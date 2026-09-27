import sqlite3
import json
import time
from contextlib import contextmanager

DB_PATH = "shop.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                lang TEXT DEFAULT 'uz',
                phone TEXT,
                full_name TEXT
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS cart_items (
                user_id INTEGER,
                product_id TEXT,
                qty INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, product_id)
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                items_json TEXT,
                total INTEGER,
                phone TEXT,
                address TEXT,
                payment_method TEXT,
                status TEXT DEFAULT 'new',
                created_at INTEGER
            )"""
        )


# ---------- users ----------

def set_lang(user_id: int, lang: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (user_id, lang) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET lang=excluded.lang",
            (user_id, lang),
        )


def get_lang(user_id: int) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT lang FROM users WHERE user_id=?", (user_id,)).fetchone()
        return row["lang"] if row else "uz"


def set_phone(user_id: int, phone: str, full_name: str = ""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (user_id, phone, full_name) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET phone=excluded.phone, full_name=excluded.full_name",
            (user_id, phone, full_name),
        )


def get_user(user_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


# ---------- cart ----------

def add_to_cart(user_id: int, product_id: str, qty: int = 1):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO cart_items (user_id, product_id, qty) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, product_id) DO UPDATE SET qty = qty + excluded.qty",
            (user_id, product_id, qty),
        )


def remove_from_cart(user_id: int, product_id: str):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM cart_items WHERE user_id=? AND product_id=?", (user_id, product_id)
        )


def get_cart(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT product_id, qty FROM cart_items WHERE user_id=?", (user_id,)
        ).fetchall()


def clear_cart(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM cart_items WHERE user_id=?", (user_id,))


def cart_count(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(qty),0) AS c FROM cart_items WHERE user_id=?", (user_id,)
        ).fetchone()
        return row["c"] or 0


# ---------- orders ----------

def create_order(user_id, items, total, phone, address, payment_method, status="new") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO orders (user_id, items_json, total, phone, address, payment_method, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, json.dumps(items, ensure_ascii=False), total, phone, address, payment_method, status, int(time.time())),
        )
        return cur.lastrowid


def set_order_status(order_id: int, status: str):
    with get_conn() as conn:
        conn.execute("UPDATE orders SET status=? WHERE order_id=?", (status, order_id))


def get_orders(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY order_id DESC", (user_id,)
        ).fetchall()


def get_order(order_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
