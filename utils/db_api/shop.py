import datetime
import secrets
import sqlite3
from typing import Any

from utils.db_api.sqlite import path_to_db


def _now() -> str:
    return datetime.datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _column_exists(db: sqlite3.Connection, table: str, column: str) -> bool:
    rows = db.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def _generate_order_id(db: sqlite3.Connection) -> str:
    # 10-значный случайный номер после префикса ORD-
    for _ in range(20):
        order_id = f"ORD-{secrets.randbelow(10**10):010d}"
        exists = db.execute("SELECT 1 FROM storage_shop_orders WHERE id = ?", (order_id,)).fetchone()
        if not exists:
            return order_id
    raise RuntimeError("Не удалось сгенерировать уникальный номер заказа")


STATUS_MAP = {
    "new": "Новый",
    "paid": "Оплачен",
    "shipped": "Отправлен",
    "done": "Доставлен",
    "cancel": "Отменен",
}


def _status_ru(status: str) -> str:
    if not status:
        return "Новый"
    return STATUS_MAP.get(status, status)


def _status_from_input(status: str) -> str:
    if not status:
        return "Новый"
    return STATUS_MAP.get(status, status)


def init_shop_tables() -> None:
    with sqlite3.connect(path_to_db) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_shop_users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                name TEXT,
                phone TEXT,
                address TEXT,
                created_at TEXT
            )
            """
        )
        if not _column_exists(db, "storage_shop_users", "role"):
            db.execute("ALTER TABLE storage_shop_users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_shop_categories(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_shop_products(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price INTEGER NOT NULL,
                stock INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                photo TEXT,
                brand TEXT,
                created_at TEXT
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_shop_cart(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                created_at TEXT,
                UNIQUE(user_id, product_id)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_shop_wishlist(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                created_at TEXT,
                UNIQUE(user_id, product_id)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_shop_orders(
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                total_price INTEGER NOT NULL,
                status TEXT NOT NULL,
                delivery TEXT,
                payment TEXT,
                customer_name TEXT,
                customer_phone TEXT,
                customer_address TEXT,
                created_at TEXT
            )
            """
        )
        if not _column_exists(db, "storage_shop_orders", "receipt_file_id"):
            db.execute("ALTER TABLE storage_shop_orders ADD COLUMN receipt_file_id TEXT NOT NULL DEFAULT ''")
        if not _column_exists(db, "storage_shop_orders", "receipt_file_type"):
            db.execute("ALTER TABLE storage_shop_orders ADD COLUMN receipt_file_type TEXT NOT NULL DEFAULT ''")
        if not _column_exists(db, "storage_shop_orders", "receipt_sent_at"):
            db.execute("ALTER TABLE storage_shop_orders ADD COLUMN receipt_sent_at TEXT NOT NULL DEFAULT ''")
        if not _column_exists(db, "storage_shop_orders", "receipt_review_status"):
            db.execute("ALTER TABLE storage_shop_orders ADD COLUMN receipt_review_status TEXT NOT NULL DEFAULT ''")
        if not _column_exists(db, "storage_shop_orders", "receipt_reviewed_at"):
            db.execute("ALTER TABLE storage_shop_orders ADD COLUMN receipt_reviewed_at TEXT NOT NULL DEFAULT ''")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_shop_order_items(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                price INTEGER NOT NULL,
                title TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_shop_settings(
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )

        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('maintenance', '0')")
        db.execute(
            "INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('welcome_text', 'Добро пожаловать в магазин электроники')"
        )
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('welcome_photo', '')")
        db.execute(
            """
            INSERT OR IGNORE INTO storage_shop_settings(key, value)
            VALUES ('notif_admin_new_order_tpl', '<b>🆕 Новый заказ</b>\nНомер: <code>{order_id}</code>\nКлиент: <b>{name}</b>\nТелефон: <b>{phone}</b>\nСумма: <b>{total} грн</b>\nДоставка: <b>{delivery}</b>\nОплата: <b>{payment}</b>')
            """
        )
        db.execute(
            """
            INSERT OR IGNORE INTO storage_shop_settings(key, value)
            VALUES ('notif_user_status_tpl', '<b>🔔 Обновление заказа</b>\nНомер: <code>{order_id}</code>\nНовый статус: <b>{status}</b>')
            """
        )
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('notify_chat_id', '')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('payment_card_info', '')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('payment_applepay_info', '')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('payment_googlepay_info', '')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('payment_cod_enabled', '1')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('support_admin_ids', '')")

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_support_tickets(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT,
                closed_at TEXT DEFAULT '',
                media_file_id TEXT DEFAULT '',
                media_type TEXT DEFAULT ''
            )
            """
        )
        if not _column_exists(db, "storage_support_tickets", "closed_at"):
            db.execute("ALTER TABLE storage_support_tickets ADD COLUMN closed_at TEXT DEFAULT ''")
        if not _column_exists(db, "storage_support_tickets", "media_file_id"):
            db.execute("ALTER TABLE storage_support_tickets ADD COLUMN media_file_id TEXT DEFAULT ''")
        if not _column_exists(db, "storage_support_tickets", "media_type"):
            db.execute("ALTER TABLE storage_support_tickets ADD COLUMN media_type TEXT DEFAULT ''")

        for category in ["Смартфоны", "Ноутбуки", "Аксессуары", "Запчасти"]:
            db.execute("INSERT OR IGNORE INTO storage_shop_categories(name) VALUES (?)", (category,))

        from data.config import adm, sozdatel

        owner_id = str(sozdatel).strip()
        if owner_id:
            db.execute(
                "INSERT OR IGNORE INTO storage_shop_users(telegram_id, name, created_at, role) VALUES (?, '', ?, 'owner')",
                (int(owner_id), _now()),
            )
            db.execute("UPDATE storage_shop_users SET role = 'owner' WHERE telegram_id = ?", (int(owner_id),))

        for admin_id in adm:
            admin_id = str(admin_id).strip()
            if not admin_id or admin_id == owner_id:
                continue
            db.execute(
                "INSERT OR IGNORE INTO storage_shop_users(telegram_id, name, created_at, role) VALUES (?, '', ?, 'admin')",
                (int(admin_id), _now()),
            )
            db.execute(
                "UPDATE storage_shop_users SET role = 'admin' WHERE telegram_id = ? AND role != 'owner'",
                (int(admin_id),),
            )

        db.commit()


def get_shop_setting(key: str, default: str = "") -> str:
    with sqlite3.connect(path_to_db) as db:
        row = db.execute("SELECT value FROM storage_shop_settings WHERE key = ?", (key,)).fetchone()
    if not row or row[0] is None:
        return default
    return str(row[0])


def set_shop_setting(key: str, value: str) -> None:
    with sqlite3.connect(path_to_db) as db:
        db.execute(
            "INSERT INTO storage_shop_settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        db.commit()


def get_welcome_message() -> tuple[str, str]:
    return get_shop_setting("welcome_text", "Добро пожаловать в магазин электроники"), get_shop_setting("welcome_photo", "")


def set_welcome_message(text: str, photo: str = "") -> None:
    set_shop_setting("welcome_text", text)
    set_shop_setting("welcome_photo", photo)


def is_maintenance() -> bool:
    return get_shop_setting("maintenance", "0") == "1"


def toggle_maintenance() -> bool:
    current = is_maintenance()
    set_shop_setting("maintenance", "0" if current else "1")
    return not current


def get_admin_new_order_template() -> str:
    return get_shop_setting(
        "notif_admin_new_order_tpl",
        "<b>🆕 Новый заказ</b>\nНомер: <code>{order_id}</code>\nКлиент: <b>{name}</b>\nТелефон: <b>{phone}</b>\nСумма: <b>{total} грн</b>\nДоставка: <b>{delivery}</b>\nОплата: <b>{payment}</b>",
    )


def set_admin_new_order_template(template: str) -> None:
    set_shop_setting("notif_admin_new_order_tpl", template)


def get_user_status_template() -> str:
    return get_shop_setting(
        "notif_user_status_tpl",
        "<b>🔔 Обновление заказа</b>\nНомер: <code>{order_id}</code>\nНовый статус: <b>{status}</b>",
    )


def set_user_status_template(template: str) -> None:
    set_shop_setting("notif_user_status_tpl", template)


def get_notify_chat_id() -> str:
    return get_shop_setting("notify_chat_id", "").strip()


def set_notify_chat_id(chat_id: str) -> None:
    set_shop_setting("notify_chat_id", chat_id.strip())


def render_template(template: str, context: dict[str, Any]) -> str:
    result = template
    for key, value in context.items():
        result = result.replace("{" + key + "}", str(value))
    return result


def get_payment_settings() -> dict[str, str]:
    return {
        "cod": "1" if get_shop_setting("payment_cod_enabled", "1") != "0" else "0",
        "card": get_shop_setting("payment_card_info", "").strip(),
        "applepay": get_shop_setting("payment_applepay_info", "").strip(),
        "googlepay": get_shop_setting("payment_googlepay_info", "").strip(),
    }


def set_payment_setting(method: str, value: str) -> None:
    mapping = {
        "card": "payment_card_info",
        "applepay": "payment_applepay_info",
        "googlepay": "payment_googlepay_info",
    }
    key = mapping.get(method)
    if not key:
        return
    set_shop_setting(key, value.strip())


def set_payment_enabled(method: str, enabled: bool) -> None:
    if method == "cod":
        set_shop_setting("payment_cod_enabled", "1" if enabled else "0")


def get_payment_info(method: str) -> str:
    return get_payment_settings().get(method, "")


def payment_label(method: str) -> str:
    return {
        "cod": "Наложенный платеж",
        "card": "Банковская карта",
        "applepay": "Apple Pay",
        "googlepay": "Google Pay",
    }.get(method, method)


def is_payment_enabled(method: str) -> bool:
    if method == "cod":
        return get_shop_setting("payment_cod_enabled", "1") != "0"
    return bool(get_payment_info(method))


def ensure_user(telegram_id: int, name: str = "") -> None:
    with sqlite3.connect(path_to_db) as db:
        db.execute(
            """
            INSERT OR IGNORE INTO storage_shop_users(telegram_id, name, created_at, role)
            VALUES (?, ?, ?, 'user')
            """,
            (telegram_id, name, _now()),
        )
        if name:
            # Do not overwrite an already saved full name from profile wizard.
            db.execute(
                """
                UPDATE storage_shop_users
                SET name = ?
                WHERE telegram_id = ?
                  AND (name IS NULL OR TRIM(name) = '')
                """,
                (name, telegram_id),
            )
        db.commit()


def update_user_contacts(telegram_id: int, *, name: str | None = None, phone: str | None = None, address: str | None = None) -> None:
    ensure_user(telegram_id)
    with sqlite3.connect(path_to_db) as db:
        if name is not None:
            db.execute("UPDATE storage_shop_users SET name = ? WHERE telegram_id = ?", (name, telegram_id))
        if phone is not None:
            db.execute("UPDATE storage_shop_users SET phone = ? WHERE telegram_id = ?", (phone, telegram_id))
        if address is not None:
            db.execute("UPDATE storage_shop_users SET address = ? WHERE telegram_id = ?", (address, telegram_id))
        db.commit()


def get_user_profile(telegram_id: int) -> dict[str, Any]:
    ensure_user(telegram_id)
    with sqlite3.connect(path_to_db) as db:
        row = db.execute(
            "SELECT telegram_id, name, phone, address, created_at, role FROM storage_shop_users WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()

    return {
        "telegram_id": int(row[0]),
        "name": row[1] or "",
        "phone": row[2] or "",
        "address": row[3] or "",
        "created_at": row[4] or "",
        "role": row[5] or "user",
    }


def is_admin_user(telegram_id: int) -> bool:
    profile = get_user_profile(telegram_id)
    return profile["role"] in {"owner", "admin"}


def is_owner_user(telegram_id: int) -> bool:
    profile = get_user_profile(telegram_id)
    return profile["role"] == "owner"


def get_admin_ids() -> list[int]:
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(
            "SELECT telegram_id FROM storage_shop_users WHERE role IN ('owner', 'admin') ORDER BY CASE role WHEN 'owner' THEN 0 ELSE 1 END, created_at ASC"
        ).fetchall()
    return [int(row[0]) for row in rows if row and row[0]]


def get_support_admin_ids() -> list[int]:
    raw = get_shop_setting("support_admin_ids", "").strip()
    if not raw:
        return []
    ids: list[int] = []
    for part in raw.split(","):
        token = part.strip()
        if token.isdigit():
            ids.append(int(token))
    return ids


def is_support_admin(telegram_id: int) -> bool:
    return int(telegram_id) in set(get_support_admin_ids())


def set_support_admin(telegram_id: int, enabled: bool) -> None:
    user_id = int(telegram_id)
    profile = get_user_profile(user_id)
    if profile["role"] not in {"owner", "admin"}:
        return

    ids = set(get_support_admin_ids())
    if enabled:
        ids.add(user_id)
    else:
        ids.discard(user_id)
    value = ",".join(str(i) for i in sorted(ids))
    set_shop_setting("support_admin_ids", value)


def create_support_ticket(
    user_id: int,
    username: str,
    first_name: str,
    message: str,
    media_file_id: str = "",
    media_type: str = "",
) -> int:
    with sqlite3.connect(path_to_db) as db:
        cursor = db.execute(
            """
            INSERT INTO storage_support_tickets(
                user_id, username, first_name, message, status, created_at, media_file_id, media_type
            ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (user_id, username or "", first_name or "", message, _now(), media_file_id or "", media_type or ""),
        )
        db.commit()
        return cursor.lastrowid


def get_support_tickets(status: str | None = None) -> list[dict]:
    with sqlite3.connect(path_to_db) as db:
        if status:
            rows = db.execute(
                """
                SELECT id, user_id, username, first_name, message, status, created_at, media_file_id, media_type
                FROM storage_support_tickets
                WHERE status = ?
                ORDER BY created_at DESC
                """,
                (status,),
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT id, user_id, username, first_name, message, status, created_at, media_file_id, media_type
                FROM storage_support_tickets
                ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, created_at DESC
                """
            ).fetchall()
    return [
        {
            "id": r[0],
            "user_id": r[1],
            "username": r[2] or "",
            "first_name": r[3] or "",
            "message": r[4] or "",
            "status": r[5] or "active",
            "created_at": r[6] or "",
            "media_file_id": r[7] or "",
            "media_type": r[8] or "",
        }
        for r in rows
    ]


def get_support_ticket(ticket_id: int) -> dict | None:
    with sqlite3.connect(path_to_db) as db:
        r = db.execute(
            """
            SELECT id, user_id, username, first_name, message, status, created_at, media_file_id, media_type
            FROM storage_support_tickets
            WHERE id = ?
            """,
            (ticket_id,),
        ).fetchone()
    if not r:
        return None
    return {
        "id": r[0],
        "user_id": r[1],
        "username": r[2] or "",
        "first_name": r[3] or "",
        "message": r[4] or "",
        "status": r[5] or "active",
        "created_at": r[6] or "",
        "media_file_id": r[7] or "",
        "media_type": r[8] or "",
    }


def close_support_ticket(ticket_id: int) -> None:
    with sqlite3.connect(path_to_db) as db:
        db.execute(
            "UPDATE storage_support_tickets SET status = 'closed', closed_at = ? WHERE id = ?",
            (_now(), ticket_id),
        )
        db.commit()


def delete_old_closed_tickets(days: int = 7) -> int:
    """Delete closed tickets older than `days` days. Returns count deleted."""
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).replace(microsecond=0).isoformat(sep=" ")
    with sqlite3.connect(path_to_db) as db:
        cursor = db.execute(
            "DELETE FROM storage_support_tickets WHERE status = 'closed' AND closed_at != '' AND closed_at <= ?",
            (cutoff,),
        )
        db.commit()
        return cursor.rowcount


def set_user_role(telegram_id: int, role: str, name: str = "") -> None:
    if role not in {"owner", "admin", "user"}:
        return
    ensure_user(telegram_id, name)
    with sqlite3.connect(path_to_db) as db:
        db.execute("UPDATE storage_shop_users SET role = ? WHERE telegram_id = ?", (role, telegram_id))
        db.commit()


def add_admin_user(telegram_id: int, name: str = "") -> None:
    set_user_role(telegram_id, "admin", name)


def remove_admin_user(telegram_id: int) -> bool:
    if is_owner_user(telegram_id):
        return False
    set_user_role(telegram_id, "user")
    return True


def list_admin_users() -> list[dict[str, Any]]:
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(
            """
            SELECT telegram_id, name, phone, address, created_at, role
            FROM storage_shop_users
            WHERE role IN ('owner', 'admin')
            ORDER BY CASE role WHEN 'owner' THEN 0 ELSE 1 END, created_at DESC
            """
        ).fetchall()
    return [
        {
            "telegram_id": int(row[0]),
            "name": row[1] or "Без имени",
            "phone": row[2] or "",
            "address": row[3] or "",
            "created_at": row[4] or "",
            "role": row[5] or "user",
        }
        for row in rows
    ]


def list_customer_users(limit: int = 200) -> list[dict[str, Any]]:
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(
            """
            SELECT telegram_id, name, phone, address, created_at, role
            FROM storage_shop_users
            WHERE role = 'user'
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "telegram_id": int(row[0]),
            "name": row[1] or "Без имени",
            "phone": row[2] or "",
            "address": row[3] or "",
            "created_at": row[4] or "",
            "role": row[5] or "user",
        }
        for row in rows
    ]


def list_categories() -> list[dict[str, Any]]:
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute("SELECT id, name FROM storage_shop_categories ORDER BY id").fetchall()
    return [{"id": int(row[0]), "name": row[1]} for row in rows]


def get_or_create_category(name: str) -> int:
    with sqlite3.connect(path_to_db) as db:
        row = db.execute("SELECT id FROM storage_shop_categories WHERE name = ?", (name,)).fetchone()
        if row:
            return int(row[0])
        cur = db.execute("INSERT INTO storage_shop_categories(name) VALUES (?)", (name,))
        db.commit()
        return int(cur.lastrowid)


def create_category(name: str) -> tuple[bool, str, int | None]:
    category_name = name.strip()
    if not category_name:
        return False, "Название категории не может быть пустым", None

    with sqlite3.connect(path_to_db) as db:
        row = db.execute("SELECT id FROM storage_shop_categories WHERE lower(name) = lower(?)", (category_name,)).fetchone()
        if row:
            return False, "Такая категория уже существует", int(row[0])
        cur = db.execute("INSERT INTO storage_shop_categories(name) VALUES (?)", (category_name,))
        db.commit()
        return True, "Категория создана", int(cur.lastrowid)


def delete_category(category_id: int) -> tuple[bool, str]:
    with sqlite3.connect(path_to_db) as db:
        row = db.execute("SELECT name FROM storage_shop_categories WHERE id = ?", (category_id,)).fetchone()
        if not row:
            return False, "Категория не найдена"

        products_count = db.execute(
            "SELECT COUNT(*) FROM storage_shop_products WHERE category_id = ?",
            (category_id,),
        ).fetchone()[0]
        if int(products_count) > 0:
            return False, "Нельзя удалить категорию, пока в ней есть товары"

        db.execute("DELETE FROM storage_shop_categories WHERE id = ?", (category_id,))
        db.commit()
        return True, f"Категория '{row[0]}' удалена"


def create_product(name: str, description: str, price: int, stock: int, category_id: int, photo: str = "", brand: str = "") -> int:
    with sqlite3.connect(path_to_db) as db:
        cur = db.execute(
            """
            INSERT INTO storage_shop_products(name, description, price, stock, category_id, photo, brand, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, description, int(price), int(stock), int(category_id), photo, brand, _now()),
        )
        db.commit()
        return int(cur.lastrowid)


def update_product(product_id: int, **kwargs: Any) -> None:
    if not kwargs:
        return
    keys = [k for k in kwargs.keys() if k in {"name", "description", "price", "stock", "category_id", "photo", "brand"}]
    if not keys:
        return

    values = [kwargs[k] for k in keys]
    set_sql = ", ".join([f"{k} = ?" for k in keys])

    with sqlite3.connect(path_to_db) as db:
        db.execute(f"UPDATE storage_shop_products SET {set_sql} WHERE id = ?", (*values, product_id))
        db.commit()


def delete_product(product_id: int) -> None:
    with sqlite3.connect(path_to_db) as db:
        db.execute("DELETE FROM storage_shop_cart WHERE product_id = ?", (product_id,))
        db.execute("DELETE FROM storage_shop_products WHERE id = ?", (product_id,))
        db.commit()


def get_product(product_id: int) -> dict[str, Any] | None:
    with sqlite3.connect(path_to_db) as db:
        row = db.execute(
            """
            SELECT p.id, p.name, p.description, p.price, p.stock, p.category_id, p.photo, p.brand, c.name
            FROM storage_shop_products p
            LEFT JOIN storage_shop_categories c ON c.id = p.category_id
            WHERE p.id = ?
            """,
            (product_id,),
        ).fetchone()

    if not row:
        return None

    return {
        "id": int(row[0]),
        "name": row[1],
        "description": row[2] or "",
        "price": int(row[3]),
        "stock": int(row[4]),
        "category_id": int(row[5]),
        "photo": row[6] or "",
        "brand": row[7] or "",
        "category_name": row[8] or "",
    }


def list_products(category_id: int | None = None, search: str | None = None, only_available: bool = True) -> list[dict[str, Any]]:
    return list_products_paginated(
        category_id=category_id,
        search=search,
        only_available=only_available,
        page=1,
        per_page=500,
    )[0]


def _build_products_where(
    *,
    category_id: int | None = None,
    search: str | None = None,
    only_available: bool | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    brand: str | None = None,
) -> tuple[str, list[Any]]:
    sql = (
        "SELECT p.id, p.name, p.description, p.price, p.stock, p.category_id, p.photo, p.brand, c.name "
        "FROM storage_shop_products p "
        "LEFT JOIN storage_shop_categories c ON c.id = p.category_id WHERE 1=1"
    )
    params: list[Any] = []

    if category_id is not None:
        sql += " AND p.category_id = ?"
        params.append(category_id)
    if search:
        sql += " AND (LOWER(p.name) LIKE ? OR LOWER(p.description) LIKE ? OR LOWER(COALESCE(p.brand, '')) LIKE ?)"
        needle = f"%{search.lower()}%"
        params.extend([needle, needle, needle])
    if only_available:
        sql += " AND p.stock > 0"

    if min_price is not None:
        sql += " AND p.price >= ?"
        params.append(int(min_price))

    if max_price is not None:
        sql += " AND p.price <= ?"
        params.append(int(max_price))

    if brand:
        sql += " AND LOWER(COALESCE(p.brand, '')) = ?"
        params.append(brand.lower())

    return sql, params


def list_products_paginated(
    *,
    category_id: int | None = None,
    search: str | None = None,
    only_available: bool | None = True,
    min_price: int | None = None,
    max_price: int | None = None,
    brand: str | None = None,
    page: int = 1,
    per_page: int = 6,
) -> tuple[list[dict[str, Any]], int]:
    sql, params = _build_products_where(
        category_id=category_id,
        search=search,
        only_available=only_available,
        min_price=min_price,
        max_price=max_price,
        brand=brand,
    )

    count_sql = sql.replace(
        "SELECT p.id, p.name, p.description, p.price, p.stock, p.category_id, p.photo, p.brand, c.name",
        "SELECT COUNT(*)",
    )

    page = max(1, int(page))
    per_page = max(1, int(per_page))
    offset = (page - 1) * per_page

    sql += " ORDER BY p.id DESC LIMIT ? OFFSET ?"

    with sqlite3.connect(path_to_db) as db:
        total = int(db.execute(count_sql, params).fetchone()[0])
        rows = db.execute(sql, [*params, per_page, offset]).fetchall()

    items = [
        {
            "id": int(row[0]),
            "name": row[1],
            "description": row[2] or "",
            "price": int(row[3]),
            "stock": int(row[4]),
            "category_id": int(row[5]),
            "photo": row[6] or "",
            "brand": row[7] or "",
            "category_name": row[8] or "",
        }
        for row in rows
    ]

    return items, total


def list_brands(category_id: int | None = None) -> list[str]:
    sql = "SELECT DISTINCT brand FROM storage_shop_products WHERE TRIM(COALESCE(brand, '')) != ''"
    params: list[Any] = []
    if category_id is not None:
        sql += " AND category_id = ?"
        params.append(category_id)
    sql += " ORDER BY brand"

    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(sql, params).fetchall()
    return [str(row[0]) for row in rows if row and row[0]]


def wishlist_add(user_id: int, product_id: int) -> None:
    with sqlite3.connect(path_to_db) as db:
        db.execute(
            "INSERT OR IGNORE INTO storage_shop_wishlist(user_id, product_id, created_at) VALUES (?, ?, ?)",
            (user_id, product_id, _now()),
        )
        db.commit()


def wishlist_remove(user_id: int, product_id: int) -> None:
    with sqlite3.connect(path_to_db) as db:
        db.execute("DELETE FROM storage_shop_wishlist WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        db.commit()


def wishlist_has(user_id: int, product_id: int) -> bool:
    with sqlite3.connect(path_to_db) as db:
        row = db.execute(
            "SELECT 1 FROM storage_shop_wishlist WHERE user_id = ? AND product_id = ? LIMIT 1",
            (user_id, product_id),
        ).fetchone()
    return bool(row)


def wishlist_toggle(user_id: int, product_id: int) -> bool:
    if wishlist_has(user_id, product_id):
        wishlist_remove(user_id, product_id)
        return False
    wishlist_add(user_id, product_id)
    return True


def wishlist_list(user_id: int) -> list[dict[str, Any]]:
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(
            """
            SELECT p.id, p.name, p.description, p.price, p.stock, p.category_id, p.photo, p.brand, c.name
            FROM storage_shop_wishlist w
            JOIN storage_shop_products p ON p.id = w.product_id
            LEFT JOIN storage_shop_categories c ON c.id = p.category_id
            WHERE w.user_id = ?
            ORDER BY w.id DESC
            """,
            (user_id,),
        ).fetchall()

    return [
        {
            "id": int(row[0]),
            "name": row[1],
            "description": row[2] or "",
            "price": int(row[3]),
            "stock": int(row[4]),
            "category_id": int(row[5]),
            "photo": row[6] or "",
            "brand": row[7] or "",
            "category_name": row[8] or "",
        }
        for row in rows
    ]


def add_to_cart(user_id: int, product_id: int, quantity: int = 1) -> tuple[bool, str]:
    product = get_product(product_id)
    if not product:
        return False, "Товар не найден"
    if product["stock"] <= 0:
        return False, "❌ Нет в наличии"

    with sqlite3.connect(path_to_db) as db:
        row = db.execute(
            "SELECT quantity FROM storage_shop_cart WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        ).fetchone()
        current_qty = int(row[0]) if row else 0
        new_qty = current_qty + int(quantity)

        if new_qty > product["stock"]:
            return False, "Недостаточно товара на складе"

        if row:
            db.execute(
                "UPDATE storage_shop_cart SET quantity = ? WHERE user_id = ? AND product_id = ?",
                (new_qty, user_id, product_id),
            )
        else:
            db.execute(
                "INSERT INTO storage_shop_cart(user_id, product_id, quantity, created_at) VALUES (?, ?, ?, ?)",
                (user_id, product_id, quantity, _now()),
            )

        db.commit()

    return True, "🛒 Добавлено в корзину"


def remove_from_cart(user_id: int, product_id: int) -> None:
    with sqlite3.connect(path_to_db) as db:
        db.execute("DELETE FROM storage_shop_cart WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        db.commit()


def update_cart_quantity(user_id: int, product_id: int, quantity: int) -> tuple[bool, str]:
    if quantity <= 0:
        remove_from_cart(user_id, product_id)
        return True, "Позиция удалена"

    product = get_product(product_id)
    if not product:
        return False, "Товар не найден"
    if quantity > product["stock"]:
        return False, "Недостаточно товара на складе"

    with sqlite3.connect(path_to_db) as db:
        db.execute(
            "UPDATE storage_shop_cart SET quantity = ? WHERE user_id = ? AND product_id = ?",
            (quantity, user_id, product_id),
        )
        db.commit()

    return True, "Количество обновлено"


def change_cart_quantity(user_id: int, product_id: int, delta: int) -> tuple[bool, str]:
    with sqlite3.connect(path_to_db) as db:
        row = db.execute(
            "SELECT quantity FROM storage_shop_cart WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        ).fetchone()
    if not row:
        return False, "Позиция не найдена"

    return update_cart_quantity(user_id, product_id, int(row[0]) + int(delta))


def clear_cart(user_id: int) -> None:
    with sqlite3.connect(path_to_db) as db:
        db.execute("DELETE FROM storage_shop_cart WHERE user_id = ?", (user_id,))
        db.commit()


def get_cart(user_id: int) -> list[dict[str, Any]]:
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(
            """
            SELECT c.product_id, c.quantity, p.name, p.price, p.stock
            FROM storage_shop_cart c
            JOIN storage_shop_products p ON p.id = c.product_id
            WHERE c.user_id = ?
            ORDER BY c.id DESC
            """,
            (user_id,),
        ).fetchall()

    return [
        {
            "position_id": int(row[0]),
            "product_id": int(row[0]),
            "quantity": int(row[1]),
            "title": row[2],
            "price": int(row[3]),
            "stock": int(row[4]),
            "sum": int(row[1]) * int(row[3]),
        }
        for row in rows
    ]


def cart_total(user_id: int) -> int:
    return sum(item["sum"] for item in get_cart(user_id))


def create_order_from_cart(user_id: int, *, name: str, phone: str, address: str, delivery: str, payment: str) -> tuple[bool, str]:
    cart = get_cart(user_id)
    if not cart:
        return False, "Корзина пустая"

    total = sum(item["sum"] for item in cart)

    with sqlite3.connect(path_to_db) as db:
        try:
            order_id = _generate_order_id(db)
            for item in cart:
                row = db.execute("SELECT stock FROM storage_shop_products WHERE id = ?", (item["product_id"],)).fetchone()
                if not row or int(row[0]) < item["quantity"]:
                    db.rollback()
                    return False, f"Недостаточно товара: {item['title']}"

            for item in cart:
                db.execute(
                    "UPDATE storage_shop_products SET stock = stock - ? WHERE id = ?",
                    (item["quantity"], item["product_id"]),
                )

            db.execute(
                """
                INSERT INTO storage_shop_orders(
                    id, user_id, total_price, status, delivery, payment,
                    customer_name, customer_phone, customer_address, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (order_id, user_id, total, "Новый", delivery, payment, name, phone, address, _now()),
            )

            for item in cart:
                db.execute(
                    """
                    INSERT INTO storage_shop_order_items(order_id, product_id, quantity, price, title)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (order_id, item["product_id"], item["quantity"], item["price"], item["title"]),
                )

            db.execute("DELETE FROM storage_shop_cart WHERE user_id = ?", (user_id,))
            db.commit()
        except Exception:
            db.rollback()
            return False, "Не удалось оформить заказ"

    update_user_contacts(user_id, name=name, phone=phone, address=address)
    return True, order_id


def get_user_orders(user_id: int) -> list[dict[str, Any]]:
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(
            """
            SELECT id, total_price, status, delivery, payment, created_at
            FROM storage_shop_orders
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()

    return [
        {
            "order_id": row[0],
            "total": int(row[1]),
            "status": _status_ru(row[2]),
            "status_raw": row[2] or "",
            "delivery": row[3] or "",
            "payment": row[4] or "",
            "created_at": row[5] or "",
        }
        for row in rows
    ]


def get_order_items(order_id: str) -> list[dict[str, Any]]:
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(
            "SELECT title, price, quantity FROM storage_shop_order_items WHERE order_id = ?",
            (order_id,),
        ).fetchall()

    return [{"title": row[0], "price": int(row[1]), "quantity": int(row[2])} for row in rows]


def get_order(order_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(path_to_db) as db:
        row = db.execute(
            """
            SELECT id, user_id, total_price, status, delivery, payment,
                   customer_name, customer_phone, customer_address, created_at,
                     receipt_file_id, receipt_file_type, receipt_sent_at,
                     receipt_review_status, receipt_reviewed_at
            FROM storage_shop_orders WHERE id = ?
            """,
            (order_id,),
        ).fetchone()
    if not row:
        return None

    return {
        "order_id": row[0],
        "user_id": int(row[1]),
        "total": int(row[2]),
        "status": _status_ru(row[3]),
        "status_raw": row[3] or "",
        "delivery": row[4] or "",
        "payment": row[5] or "",
        "name": row[6] or "",
        "phone": row[7] or "",
        "address": row[8] or "",
        "created_at": row[9] or "",
        "receipt_file_id": row[10] or "",
        "receipt_file_type": row[11] or "",
        "receipt_sent_at": row[12] or "",
        "receipt_review_status": row[13] or "",
        "receipt_reviewed_at": row[14] or "",
        "receipt_sent": bool((row[10] or "").strip()),
    }


def save_order_receipt(order_id: str, *, file_id: str, file_type: str) -> bool:
    with sqlite3.connect(path_to_db) as db:
        row = db.execute(
            "SELECT receipt_file_id, receipt_review_status FROM storage_shop_orders WHERE id = ?",
            (order_id,),
        ).fetchone()
        if not row:
            return False
        existing_file = str(row[0] or "").strip()
        review_status = str(row[1] or "").strip().lower()
        if existing_file and review_status != "rejected":
            return False
        db.execute(
            """
            UPDATE storage_shop_orders
            SET receipt_file_id = ?,
                receipt_file_type = ?,
                receipt_sent_at = ?,
                receipt_review_status = 'pending',
                receipt_reviewed_at = ''
            WHERE id = ?
            """,
            (file_id, file_type, _now(), order_id),
        )
        db.commit()
    return True


def set_order_receipt_review_status(order_id: str, status: str) -> bool:
    normalized = str(status or "").strip().lower()
    if normalized not in {"approved", "rejected"}:
        return False

    with sqlite3.connect(path_to_db) as db:
        row = db.execute(
            "SELECT receipt_file_id, receipt_review_status FROM storage_shop_orders WHERE id = ?",
            (order_id,),
        ).fetchone()
        if not row:
            return False

        receipt_file_id = str(row[0] or "").strip()
        current_status = str(row[1] or "").strip().lower()
        if not receipt_file_id:
            return False
        if current_status not in {"", "pending"}:
            return False

        db.execute(
            """
            UPDATE storage_shop_orders
            SET receipt_review_status = ?, receipt_reviewed_at = ?
            WHERE id = ?
            """,
            (normalized, _now(), order_id),
        )
        db.commit()
    return True


def list_all_orders(limit: int = 50) -> list[dict[str, Any]]:
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(
            """
            SELECT id, user_id, total_price, status, created_at, receipt_file_id, receipt_review_status
            FROM storage_shop_orders
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "order_id": row[0],
            "user_id": int(row[1]),
            "total": int(row[2]),
            "status": _status_ru(row[3]),
            "status_raw": row[3] or "",
            "created_at": row[4] or "",
            "receipt_sent": bool((row[5] or "").strip()),
            "receipt_review_status": row[6] or "",
        }
        for row in rows
    ]


def update_order_status(order_id: str, status: str) -> None:
    status_ru = _status_from_input(status)
    with sqlite3.connect(path_to_db) as db:
        db.execute("UPDATE storage_shop_orders SET status = ? WHERE id = ?", (status_ru, order_id))
        db.commit()


def get_admin_products() -> list[dict[str, Any]]:
    return list_products(only_available=False)


def get_all_user_ids_for_broadcast() -> list[int]:
    result: set[int] = set()
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute("SELECT user_id FROM storage_users").fetchall()
        for row in rows:
            if row and row[0]:
                result.add(int(row[0]))

        rows2 = db.execute("SELECT telegram_id FROM storage_shop_users").fetchall()
        for row in rows2:
            if row and row[0]:
                result.add(int(row[0]))

    return sorted(result)


def get_shop_stats() -> dict[str, int]:
    with sqlite3.connect(path_to_db) as db:
        products = db.execute("SELECT COUNT(*) FROM storage_shop_products").fetchone()[0]
        categories = db.execute("SELECT COUNT(*) FROM storage_shop_categories").fetchone()[0]
        customers = db.execute("SELECT COUNT(*) FROM storage_shop_users WHERE role='user'").fetchone()[0]
        admins = db.execute("SELECT COUNT(*) FROM storage_shop_users WHERE role IN ('admin', 'owner')").fetchone()[0]
        orders = db.execute("SELECT COUNT(*) FROM storage_shop_orders").fetchone()[0]
        orders_new = db.execute("SELECT COUNT(*) FROM storage_shop_orders WHERE status='Новый'").fetchone()[0]
        orders_inwork = db.execute("SELECT COUNT(*) FROM storage_shop_orders WHERE status IN ('Оплачен', 'Отправлен')").fetchone()[0]
        orders_archive = db.execute("SELECT COUNT(*) FROM storage_shop_orders WHERE status IN ('Доставлен', 'Отменен')").fetchone()[0]
        revenue = db.execute("SELECT COALESCE(SUM(total_price),0) FROM storage_shop_orders").fetchone()[0]
    return {
        "products": int(products),
        "categories": int(categories),
        "customers": int(customers),
        "admins": int(admins),
        "orders": int(orders),
        "orders_new": int(orders_new),
        "orders_inwork": int(orders_inwork),
        "orders_archive": int(orders_archive),
        "revenue": int(revenue),
    }
