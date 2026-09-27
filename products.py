import json
from pathlib import Path

_PRODUCTS_PATH = Path(__file__).parent / "data" / "products.json"


def load_products():
    with open(_PRODUCTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_product(product_id: str):
    for p in load_products():
        if p["id"] == product_id:
            return p
    return None


def format_price(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")
