import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://example.com")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0") or 0)
CURRENCY = os.getenv("CURRENCY", "UZS")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi! .env faylini .env.example dan nusxa olib to'ldiring."
    )
