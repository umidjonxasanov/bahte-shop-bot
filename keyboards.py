from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)
from texts import t
import config


def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O'ZBEKCHA", callback_data="lang:uz"),
                InlineKeyboardButton(text="🇷🇺 РУССКИЙ", callback_data="lang:ru"),
            ]
        ]
    )


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("menu_site", lang), web_app=WebAppInfo(url=config.WEBSITE_URL))],
            [KeyboardButton(text=t("menu_catalog", lang)), KeyboardButton(text=t("menu_cart", lang))],
            [KeyboardButton(text=t("menu_orders", lang)), KeyboardButton(text=t("menu_lang", lang))],
        ],
        resize_keyboard=True,
    )


def product_keyboard(product: dict, lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t("add_to_cart", lang), callback_data=f"add:{product['id']}")],
    ]
    site_url = product.get("site_url") or config.WEBSITE_URL
    if site_url.startswith("https://"):
        rows.append(
            [InlineKeyboardButton(text=t("details", lang), web_app=WebAppInfo(url=site_url))]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_item_keyboard(product_id: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("remove_item_btn", lang), callback_data=f"rm:{product_id}")]
        ]
    )


def cart_actions_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("checkout_btn", lang), callback_data="checkout")],
            [InlineKeyboardButton(text=t("clear_cart_btn", lang), callback_data="clear_cart")],
        ]
    )


def phone_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("share_phone_btn", lang), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def payment_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = []
    if config.PAYMENT_PROVIDER_TOKEN:
        rows.append([InlineKeyboardButton(text=t("pay_online_btn", lang), callback_data="pay:online")])
    rows.append([InlineKeyboardButton(text=t("pay_cash_btn", lang), callback_data="pay:cash")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def site_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("open_site_btn", lang), web_app=WebAppInfo(url=config.WEBSITE_URL))]
        ]
    )
