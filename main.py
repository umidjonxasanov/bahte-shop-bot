import asyncio
import logging

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    LabeledPrice,
    PreCheckoutQuery,
    FSInputFile,
)

import config
import database as db
from products import load_products, get_product, format_price
from texts import t, TXT
import keyboards as kb

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("shopbot")

router = Router()


class Checkout(StatesGroup):
    waiting_phone = State()
    waiting_address = State()


def is_menu_button(message_text: str, key: str) -> bool:
    return message_text in (TXT[key]["uz"], TXT[key]["ru"])


def build_cart_text(user_id: int, lang: str):
    items = db.get_cart(user_id)
    if not items:
        return None, 0, []
    lines = []
    total = 0
    detailed = []
    for row in items:
        product = get_product(row["product_id"])
        if not product:
            continue
        qty = row["qty"]
        subtotal = product["price"] * qty
        total += subtotal
        lines.append(f"▫️ {product['name'][lang]} × {qty} — {format_price(subtotal)} so'm")
        detailed.append({"id": product["id"], "name": product["name"][lang], "qty": qty, "price": product["price"]})
    text = t("cart_header", lang) + "\n".join(lines) + t("cart_total", lang, total=format_price(total))
    return text, total, detailed


# ---------------- /start & language ----------------

@router.message(CommandStart())
async def cmd_start(message: Message):
    lang = db.get_lang(message.from_user.id)
    await message.answer(TXT["choose_lang"], reply_markup=kb.lang_keyboard())


@router.callback_query(F.data.startswith("lang:"))
async def on_lang_chosen(call: CallbackQuery):
    lang = call.data.split(":")[1]
    db.set_lang(call.from_user.id, lang)
    await call.message.delete()
    await call.message.answer(t("welcome", lang), reply_markup=kb.main_menu(lang))
    await call.answer()


@router.message(lambda m: is_menu_button(m.text or "", "menu_lang"))
async def on_change_lang(message: Message):
    await message.answer(TXT["choose_lang"], reply_markup=kb.lang_keyboard())


# ---------------- catalog ----------------

@router.message(lambda m: is_menu_button(m.text or "", "menu_catalog"))
async def show_catalog(message: Message):
    lang = db.get_lang(message.from_user.id)
    products = load_products()
    for product in products:
        caption = (
            f"*{product['name'][lang]}*\n\n"
            f"{product['desc'][lang]}\n\n"
            f"💰 *{format_price(product['price'])} so'm*"
        )
        await message.answer_photo(
            photo=product["photo"],
            caption=caption,
            parse_mode="Markdown",
            reply_markup=kb.product_keyboard(product, lang),
        )


@router.callback_query(F.data.startswith("add:"))
async def on_add_to_cart(call: CallbackQuery):
    lang = db.get_lang(call.from_user.id)
    product_id = call.data.split(":")[1]
    db.add_to_cart(call.from_user.id, product_id, 1)
    count = db.cart_count(call.from_user.id)
    await call.answer(t("added_to_cart", lang, icon="🛒", count=count), show_alert=False)


# ---------------- cart ----------------

@router.message(lambda m: is_menu_button(m.text or "", "menu_cart"))
async def show_cart(message: Message):
    lang = db.get_lang(message.from_user.id)
    text, total, _ = build_cart_text(message.from_user.id, lang)
    if not text:
        await message.answer(t("cart_empty", lang))
        return
    await message.answer(text, reply_markup=kb.cart_actions_keyboard(lang))


@router.callback_query(F.data.startswith("rm:"))
async def on_remove_item(call: CallbackQuery):
    lang = db.get_lang(call.from_user.id)
    product_id = call.data.split(":")[1]
    db.remove_from_cart(call.from_user.id, product_id)
    await call.answer("➖ OK")
    text, total, _ = build_cart_text(call.from_user.id, lang)
    if not text:
        await call.message.edit_text(t("cart_empty", lang))
    else:
        await call.message.edit_text(text, reply_markup=kb.cart_actions_keyboard(lang))


@router.callback_query(F.data == "clear_cart")
async def on_clear_cart(call: CallbackQuery):
    lang = db.get_lang(call.from_user.id)
    db.clear_cart(call.from_user.id)
    await call.message.edit_text(t("cart_empty", lang))
    await call.answer()


# ---------------- checkout flow ----------------

@router.callback_query(F.data == "checkout")
async def on_checkout(call: CallbackQuery, state: FSMContext):
    lang = db.get_lang(call.from_user.id)
    text, total, _ = build_cart_text(call.from_user.id, lang)
    if not text:
        await call.answer(t("cart_empty", lang), show_alert=True)
        return
    user = db.get_user(call.from_user.id)
    await call.answer()
    if user and user["phone"]:
        await state.update_data(phone=user["phone"])
        await state.set_state(Checkout.waiting_address)
        await call.message.answer(t("ask_address", lang))
    else:
        await state.set_state(Checkout.waiting_phone)
        await call.message.answer(t("ask_phone", lang), reply_markup=kb.phone_keyboard(lang))


@router.message(Checkout.waiting_phone, F.contact)
async def on_phone_received(message: Message, state: FSMContext):
    lang = db.get_lang(message.from_user.id)
    phone = message.contact.phone_number
    db.set_phone(message.from_user.id, phone, message.from_user.full_name)
    await state.update_data(phone=phone)
    await state.set_state(Checkout.waiting_address)
    await message.answer(t("ask_address", lang), reply_markup=kb.main_menu(lang))


@router.message(Checkout.waiting_address, F.text)
async def on_address_received(message: Message, state: FSMContext):
    lang = db.get_lang(message.from_user.id)
    address = message.text
    await state.update_data(address=address)

    text, total, _detailed = build_cart_text(message.from_user.id, lang)
    if not text:
        await message.answer(t("cart_empty", lang))
        await state.clear()
        return

    data = await state.get_data()
    items_lines = text.split("\n", 1)[1].rsplit("\n\n", 1)[0]
    summary = t(
        "order_summary",
        lang,
        items=items_lines,
        total=format_price(total),
        phone=data.get("phone", "-"),
        address=address,
    )
    await message.answer(summary, reply_markup=kb.payment_keyboard(lang))


@router.callback_query(F.data == "pay:cash")
async def on_pay_cash(call: CallbackQuery, state: FSMContext):
    lang = db.get_lang(call.from_user.id)
    data = await state.get_data()
    text, total, detailed = build_cart_text(call.from_user.id, lang)
    if not text:
        await call.answer(t("cart_empty", lang), show_alert=True)
        return
    order_id = db.create_order(
        call.from_user.id, detailed, total, data.get("phone", ""), data.get("address", ""), "cash", status="new"
    )
    db.clear_cart(call.from_user.id)
    await state.clear()
    await call.message.edit_text(t("order_created_cash", lang, order_id=order_id))
    await call.answer()
    await notify_admin(call.bot, order_id, call.from_user, data, total, detailed, "NAQD / НАЛИЧНЫМИ")


@router.callback_query(F.data == "pay:online")
async def on_pay_online(call: CallbackQuery, state: FSMContext):
    lang = db.get_lang(call.from_user.id)
    if not config.PAYMENT_PROVIDER_TOKEN:
        await call.answer(t("no_payment_configured", lang), show_alert=True)
        return
    data = await state.get_data()
    text, total, detailed = build_cart_text(call.from_user.id, lang)
    if not text:
        await call.answer(t("cart_empty", lang), show_alert=True)
        return

    order_id = db.create_order(
        call.from_user.id, detailed, total, data.get("phone", ""), data.get("address", ""), "online", status="pending_payment"
    )
    await call.answer()
    await call.bot.send_invoice(
        chat_id=call.from_user.id,
        title=t("invoice_title", lang),
        description=t("invoice_desc", lang, order_id=order_id),
        payload=f"order:{order_id}",
        provider_token=config.PAYMENT_PROVIDER_TOKEN,
        currency=config.CURRENCY,
        prices=[LabeledPrice(label=t("invoice_title", lang), amount=total * 100)],
    )


@router.pre_checkout_query()
async def on_pre_checkout(pre_checkout_q: PreCheckoutQuery):
    await pre_checkout_q.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, state: FSMContext):
    lang = db.get_lang(message.from_user.id)
    payload = message.successful_payment.invoice_payload
    order_id = int(payload.split(":")[1])
    db.set_order_status(order_id, "paid")
    db.clear_cart(message.from_user.id)
    await state.clear()
    await message.answer(t("order_created_paid", lang, order_id=order_id), reply_markup=kb.main_menu(lang))

    order = db.get_order(order_id)
    if order:
        import json as _json
        detailed = _json.loads(order["items_json"])
        data = {"phone": order["phone"], "address": order["address"]}
        await notify_admin(message.bot, order_id, message.from_user, data, order["total"], detailed, "ONLAYN / ОНЛАЙН")


# ---------------- orders coming from the website (tg.sendData) ----------------

_PAYMENT_LABELS = {
    "cash": "payment_cash",
    "click": "payment_click",
    "payme": "payment_payme",
}


@router.message(F.web_app_data)
async def on_web_app_order(message: Message, state: FSMContext):
    """The site (site/index.html) collects cart + checkout form itself and
    calls tg.sendData(JSON.stringify(order)) + tg.close() on submit. Telegram
    delivers that JSON here as message.web_app_data.data."""
    lang = db.get_lang(message.from_user.id)
    import json as _json

    try:
        order = _json.loads(message.web_app_data.data)
        items = order.get("items", [])
        total = int(order.get("total", sum(i.get("price", 0) for i in items)))
        phone = order.get("phone", "-")
        address = order.get("address", "-")
        payment = order.get("payment", "cash")
        name = order.get("name", message.from_user.full_name)

        db.set_phone(message.from_user.id, phone, name)

        order_id = db.create_order(
            message.from_user.id,
            items,
            total,
            phone,
            address,
            payment,
            status="new" if payment == "cash" else "pending_payment",
        )

        items_text = "\n".join(f"▫️ {it.get('name','?')} — {format_price(it.get('price',0))} so'm" for it in items)
        payment_label_key = _PAYMENT_LABELS.get(payment, "payment_cash")

        await message.answer(
            t(
                "site_order_received",
                lang,
                order_id=order_id,
                items=items_text,
                total=format_price(total),
                phone=phone,
                address=address,
                payment=t(payment_label_key, lang),
            ),
            reply_markup=kb.main_menu(lang),
        )

        if payment in ("click", "payme") and config.PAYMENT_PROVIDER_TOKEN:
            await message.bot.send_invoice(
                chat_id=message.from_user.id,
                title=t("invoice_title", lang),
                description=t("invoice_desc", lang, order_id=order_id),
                payload=f"order:{order_id}",
                provider_token=config.PAYMENT_PROVIDER_TOKEN,
                currency=config.CURRENCY,
                prices=[LabeledPrice(label=t("invoice_title", lang), amount=total * 100)],
            )

        await notify_admin(
            message.bot,
            order_id,
            message.from_user,
            {"phone": phone, "address": address},
            total,
            items,
            t(payment_label_key, "uz"),
        )
    except Exception:
        log.exception("Failed to process web_app_data order")
        await message.answer(t("site_order_error", lang))


async def notify_admin(bot: Bot, order_id, user, data, total, detailed, payment_label):
    if not config.ADMIN_CHAT_ID:
        return
    items_text = "\n".join(f"▫️ {it.get('name','?')} × {it.get('qty', 1)}" for it in detailed)
    text = t(
        "admin_new_order",
        "uz",
        order_id=order_id,
        user=f"{user.full_name} (@{user.username or '-'}, id:{user.id})",
        phone=data.get("phone", "-"),
        address=data.get("address", "-"),
        items=items_text,
        total=format_price(total),
        payment=payment_label,
    )
    try:
        await bot.send_message(config.ADMIN_CHAT_ID, text)
    except Exception as e:
        log.warning("Could not notify admin: %s", e)


# ---------------- orders history ----------------

@router.message(lambda m: is_menu_button(m.text or "", "menu_orders"))
async def show_orders(message: Message):
    lang = db.get_lang(message.from_user.id)
    orders = db.get_orders(message.from_user.id)
    if not orders:
        await message.answer(t("orders_empty", lang))
        return
    lines = []
    for o in orders:
        import datetime
        date_str = datetime.datetime.fromtimestamp(o["created_at"]).strftime("%d.%m.%Y %H:%M")
        lines.append(
            t("order_line", lang, id=o["order_id"], status=o["status"].upper(), total=format_price(o["total"]), date=date_str)
        )
    await message.answer("\n".join(lines))


async def main():
    db.init_db()
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    log.info("Bot ishga tushdi...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
