import datetime
import json
import re
import secrets
import sqlite3
import string
from difflib import SequenceMatcher
from typing import Any

from data.config import DEFAULT_SHOP_MENU_CAPTION
from utils.db_api.sqlite import path_to_db

_LEGACY_WELCOME_TEXT = "Задай Текст Приветствия в Настройках"
_LEGACY_MAIN_MENU_TEXT = "<b>🏠 Главное меню</b>\n\n<i>Выберите раздел ниже</i>"


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
        if not _column_exists(db, "storage_shop_users", "bonus"):
            db.execute("ALTER TABLE storage_shop_users ADD COLUMN bonus INTEGER NOT NULL DEFAULT 0")
        if not _column_exists(db, "storage_shop_users", "cart_activity_at"):
            db.execute("ALTER TABLE storage_shop_users ADD COLUMN cart_activity_at TEXT NOT NULL DEFAULT ''")
        if not _column_exists(db, "storage_shop_users", "cart_abandon_reminder_at"):
            db.execute("ALTER TABLE storage_shop_users ADD COLUMN cart_abandon_reminder_at TEXT NOT NULL DEFAULT ''")
        if not _column_exists(db, "storage_shop_users", "referral_code"):
            db.execute("ALTER TABLE storage_shop_users ADD COLUMN referral_code TEXT NOT NULL DEFAULT ''")
        if not _column_exists(db, "storage_shop_users", "referred_by"):
            db.execute("ALTER TABLE storage_shop_users ADD COLUMN referred_by INTEGER NOT NULL DEFAULT 0")
        if not _column_exists(db, "storage_shop_users", "referral_rewarded"):
            db.execute("ALTER TABLE storage_shop_users ADD COLUMN referral_rewarded INTEGER NOT NULL DEFAULT 0")
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
            "INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('welcome_text', 'Задай Текст Приветствия в Настройках')"
        )
        db.execute(
            "UPDATE storage_shop_settings SET value = 'Задай Текст Приветствия в Настройках' "
            "WHERE key = 'welcome_text' AND value = 'Добро пожаловать в магазин электроники'"
        )
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('welcome_photo', '')")
        db.execute(
            """
            INSERT OR IGNORE INTO storage_shop_settings(key, value)
            VALUES ('notif_admin_new_order_tpl', '<b>📦 Заказ {order_id}</b>\n📌 Статус: <b>Новый</b>\n👤 Клиент: <b>{name}</b>\n📞 Телефон: <b>{phone}</b>\n🚚 Доставка: <b>{delivery}</b>\n💳 Оплата: <b>{payment}</b>\n💰 Итого: <b>{total} грн</b>')
            """
        )
        db.execute(
            "UPDATE storage_shop_settings SET value = '<b>📦 Заказ {order_id}</b>\\n📌 Статус: <b>Новый</b>\\n👤 Клиент: <b>{name}</b>\\n📞 Телефон: <b>{phone}</b>\\n🚚 Доставка: <b>{delivery}</b>\\n💳 Оплата: <b>{payment}</b>\\n💰 Итого: <b>{total} грн</b>' "
            "WHERE key = 'notif_admin_new_order_tpl' AND value = '<b>🆕 Новый заказ</b>\\nНомер: <code>{order_id}</code>\\nКлиент: <b>{name}</b>\\nТелефон: <b>{phone}</b>\\nСумма: <b>{total} грн</b>\\nДоставка: <b>{delivery}</b>\\nОплата: <b>{payment}</b>'"
        )
        db.execute(
            """
            INSERT OR IGNORE INTO storage_shop_settings(key, value)
            VALUES ('notif_user_status_tpl', '<b>📦 Заказ {order_id}</b>\n📌 Статус: <b>{status}</b>')
            """
        )
        db.execute(
            "UPDATE storage_shop_settings SET value = '<b>📦 Заказ {order_id}</b>\\n📌 Статус: <b>{status}</b>' "
            "WHERE key = 'notif_user_status_tpl' AND value = '<b>🔔 Обновление заказа</b>\\nНомер: <code>{order_id}</code>\\nНовый статус: <b>{status}</b>'"
        )
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('notify_chat_id', '')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('payment_card_info', '')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('payment_applepay_info', '')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('payment_googlepay_info', '')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('payment_cod_enabled', '1')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('support_admin_ids', '')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('delivery_nova_enabled', '1')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('delivery_city_enabled', '1')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('delivery_pickup_enabled', '1')")

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

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_product_ratings(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                created_at TEXT,
                UNIQUE(order_id, product_id)
            )
            """
        )
        if not _column_exists(db, "storage_product_ratings", "comment"):
            db.execute("ALTER TABLE storage_product_ratings ADD COLUMN comment TEXT NOT NULL DEFAULT ''")

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_shop_promocodes(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                kind TEXT NOT NULL,
                value INTEGER NOT NULL,
                max_uses INTEGER NOT NULL DEFAULT -1,
                used_count INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                valid_until TEXT NOT NULL DEFAULT '',
                target_user_id INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        if not _column_exists(db, "storage_shop_promocodes", "target_user_id"):
            db.execute("ALTER TABLE storage_shop_promocodes ADD COLUMN target_user_id INTEGER NOT NULL DEFAULT 0")

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_shop_user_promo(
                user_id INTEGER PRIMARY KEY,
                code TEXT NOT NULL
            )
            """
        )

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_shop_product_views(
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                viewed_at TEXT NOT NULL,
                PRIMARY KEY (user_id, product_id)
            )
            """
        )

        if not _column_exists(db, "storage_shop_orders", "promo_code"):
            db.execute("ALTER TABLE storage_shop_orders ADD COLUMN promo_code TEXT NOT NULL DEFAULT ''")

        db.execute(
            "INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('notif_user_status_enabled', '1')"
        )
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('referral_program_enabled', '1')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('referral_bonus_inviter', '50')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('referral_bonus_referee', '25')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('cart_abandon_hours', '3')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('cart_abandon_enabled', '1')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('business_hours_enabled', '0')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('business_hours_start', '09:00')")
        db.execute("INSERT OR IGNORE INTO storage_shop_settings(key, value) VALUES ('business_hours_end', '21:00')")

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

    _migrate_legacy_menu_branding()


def _migrate_legacy_menu_branding() -> None:
    wt = get_shop_setting("welcome_text", "")
    if wt == _LEGACY_WELCOME_TEXT:
        set_shop_setting("welcome_text", DEFAULT_SHOP_MENU_CAPTION)
    mt = get_shop_setting("main_menu_text", "")
    if mt == _LEGACY_MAIN_MENU_TEXT:
        set_shop_setting("main_menu_text", DEFAULT_SHOP_MENU_CAPTION)


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
    return get_shop_setting("welcome_text", DEFAULT_SHOP_MENU_CAPTION), get_shop_setting("welcome_photo", "")


def set_welcome_message(text: str, photo: str = "") -> None:
    set_shop_setting("welcome_text", text)
    set_shop_setting("welcome_photo", photo)


def get_main_menu_message() -> tuple[str, str]:
    return get_shop_setting("main_menu_text", DEFAULT_SHOP_MENU_CAPTION), get_shop_setting("main_menu_photo", "")


def set_main_menu_message(text: str, photo: str = "") -> None:
    set_shop_setting("main_menu_text", text)
    set_shop_setting("main_menu_photo", photo)


def get_start_command_description() -> str:
    from data.config import start_command_description as default_start_command_description

    value = get_shop_setting("start_command_description", default_start_command_description).strip()
    return value or default_start_command_description


def set_start_command_description(text: str) -> None:
    set_shop_setting("start_command_description", text)


def get_text_menus() -> dict[str, dict]:
    """Получить все текстовые меню"""
    data = get_shop_setting("text_menus", "{}")
    try:
        return json.loads(data)
    except (json.JSONDecodeError, ValueError):
        return {}


def get_text_menu(menu_id: str) -> dict | None:
    """Получить конкретное текстовое меню"""
    menus = get_text_menus()
    return menus.get(menu_id)


def set_text_menu(menu_id: str, name: str, text: str, photo: str = "") -> None:
    """Сохранить текстовое меню"""
    menus = get_text_menus()
    menus[menu_id] = {
        "name": name,
        "text": text,
        "photo": photo,
        "created_at": menus.get(menu_id, {}).get("created_at", _now()),
    }
    set_shop_setting("text_menus", json.dumps(menus, ensure_ascii=False))


def delete_text_menu(menu_id: str) -> None:
    """Удалить текстовое меню"""
    menus = get_text_menus()
    menus.pop(menu_id, None)
    set_shop_setting("text_menus", json.dumps(menus, ensure_ascii=False))


def get_delivery_settings() -> dict[str, bool]:
    """Возвращает словарь вида {'nova': True, 'city': True, 'pickup': True}."""
    return {
        "nova": get_shop_setting("delivery_nova_enabled", "1") == "1",
        "city": get_shop_setting("delivery_city_enabled", "1") == "1",
        "pickup": get_shop_setting("delivery_pickup_enabled", "1") == "1",
    }


def parse_hh_mm(value: str) -> int | None:
    """Минуты от полуночи для строки ЧЧ:ММ или H:MM. Некорректное — None."""
    raw = (value or "").strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", raw)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return None
    return h * 60 + mi


def is_business_hours_restriction_enabled() -> bool:
    return get_shop_setting("business_hours_enabled", "0") == "1"


def get_business_hours_bounds() -> tuple[str, str]:
    return get_shop_setting("business_hours_start", "09:00").strip(), get_shop_setting("business_hours_end", "21:00").strip()


def is_within_business_hours(now: datetime.datetime | None = None) -> bool:
    """Если ограничение выключено — всегда True. Учитывает интервал через полночь (начало больше конца)."""
    if not is_business_hours_restriction_enabled():
        return True
    start_s, end_s = get_business_hours_bounds()
    start_m = parse_hh_mm(start_s)
    end_m = parse_hh_mm(end_s)
    if start_m is None or end_m is None:
        return True
    cur = now or datetime.datetime.now()
    now_m = cur.hour * 60 + cur.minute
    if start_m <= end_m:
        return start_m <= now_m <= end_m
    return now_m >= start_m or now_m <= end_m


def business_hours_hint_html() -> str:
    start_s, end_s = get_business_hours_bounds()
    return f"Принимаем с <b>{start_s}</b> до <b>{end_s}</b> (время сервера, где запущен бот)."


def set_business_hours_enabled(on: bool) -> None:
    set_shop_setting("business_hours_enabled", "1" if on else "0")


def set_business_hours_time(*, start: str | None = None, end: str | None = None) -> tuple[bool, str]:
    if start is not None:
        s = start.strip()
        if parse_hh_mm(s) is None:
            return False, "Начало: формат ЧЧ:ММ, например 09:00"
        set_shop_setting("business_hours_start", s)
    if end is not None:
        e = end.strip()
        if parse_hh_mm(e) is None:
            return False, "Конец: формат ЧЧ:ММ, например 21:00"
        set_shop_setting("business_hours_end", e)
    return True, ""


def is_maintenance() -> bool:
    return get_shop_setting("maintenance", "0") == "1"


def toggle_maintenance() -> bool:
    current = is_maintenance()
    set_shop_setting("maintenance", "0" if current else "1")
    return not current


def get_admin_new_order_template() -> str:
    return get_shop_setting(
        "notif_admin_new_order_tpl",
        "<b>📦 Заказ {order_id}</b>\n📌 Статус: <b>Новый</b>\n👤 Клиент: <b>{name}</b>\n📞 Телефон: <b>{phone}</b>\n🚚 Доставка: <b>{delivery}</b>\n💳 Оплата: <b>{payment}</b>\n💰 Итого: <b>{total} грн</b>",
    )


def set_admin_new_order_template(template: str) -> None:
    set_shop_setting("notif_admin_new_order_tpl", template)


def get_user_status_template() -> str:
    return get_shop_setting(
        "notif_user_status_tpl",
        "<b>📦 Заказ {order_id}</b>\n📌 Статус: <b>{status}</b>",
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
            """
            SELECT telegram_id, name, phone, address, created_at, role, bonus,
                   referral_code, referred_by, referral_rewarded
            FROM storage_shop_users WHERE telegram_id = ?
            """,
            (telegram_id,),
        ).fetchone()

    return {
        "telegram_id": int(row[0]),
        "name": row[1] or "",
        "phone": row[2] or "",
        "address": row[3] or "",
        "created_at": row[4] or "",
        "role": row[5] or "user",
        "bonus": int(row[6]) if row[6] else 0,
        "referral_code": (row[7] or "").strip(),
        "referred_by": int(row[8] or 0),
        "referral_rewarded": bool(int(row[9] or 0)),
    }


def get_user_bonus(user_id: int) -> int:
    ensure_user(user_id)
    with sqlite3.connect(path_to_db) as db:
        row = db.execute(
            "SELECT bonus FROM storage_shop_users WHERE telegram_id = ?", (user_id,)
        ).fetchone()
    return int(row[0]) if row and row[0] else 0


def set_user_bonus(user_id: int, amount: int) -> None:
    ensure_user(user_id)
    amount = max(0, int(amount))
    with sqlite3.connect(path_to_db) as db:
        db.execute(
            "UPDATE storage_shop_users SET bonus = ? WHERE telegram_id = ?",
            (amount, user_id),
        )
        db.commit()


_REF_CODE_CHARS = string.ascii_uppercase + string.digits


def touch_cart_activity(user_id: int) -> None:
    ensure_user(user_id)
    ts = _now()
    with sqlite3.connect(path_to_db) as db:
        db.execute(
            "UPDATE storage_shop_users SET cart_activity_at = ? WHERE telegram_id = ?",
            (ts, user_id),
        )
        db.commit()


def reset_cart_reminder_state(user_id: int) -> None:
    ensure_user(user_id)
    with sqlite3.connect(path_to_db) as db:
        db.execute(
            "UPDATE storage_shop_users SET cart_activity_at = '', cart_abandon_reminder_at = '' WHERE telegram_id = ?",
            (user_id,),
        )
        db.commit()


def mark_cart_abandon_reminder_sent(user_id: int) -> None:
    ensure_user(user_id)
    with sqlite3.connect(path_to_db) as db:
        db.execute(
            "UPDATE storage_shop_users SET cart_abandon_reminder_at = ? WHERE telegram_id = ?",
            (_now(), user_id),
        )
        db.commit()


def list_cart_abandon_candidate_user_ids(hours_idle: float) -> list[int]:
    if hours_idle <= 0:
        return []
    threshold = datetime.datetime.now() - datetime.timedelta(hours=hours_idle)
    threshold = threshold.replace(microsecond=0)
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(
            """
            SELECT DISTINCT c.user_id, u.cart_activity_at, u.cart_abandon_reminder_at
            FROM storage_shop_cart c
            JOIN storage_shop_users u ON u.telegram_id = c.user_id
            """
        ).fetchall()
    out: list[int] = []
    for uid, act_at, rem_at in rows:
        act_s = (act_at or "").strip()
        if not act_s:
            continue
        try:
            act_dt = datetime.datetime.fromisoformat(act_s)
        except ValueError:
            continue
        if act_dt > threshold:
            continue
        rem_s = (rem_at or "").strip()
        if not rem_s:
            out.append(int(uid))
            continue
        try:
            rem_dt = datetime.datetime.fromisoformat(rem_s)
        except ValueError:
            out.append(int(uid))
            continue
        if act_dt > rem_dt:
            out.append(int(uid))
    return out


def get_or_create_referral_code(telegram_id: int) -> str:
    ensure_user(telegram_id)
    with sqlite3.connect(path_to_db) as db:
        row = db.execute(
            "SELECT referral_code FROM storage_shop_users WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
        existing = (row[0] or "").strip() if row else ""
        if existing:
            return existing
        for _ in range(40):
            code = "".join(secrets.choice(_REF_CODE_CHARS) for _ in range(8))
            clash = db.execute(
                "SELECT 1 FROM storage_shop_users WHERE referral_code = ?",
                (code,),
            ).fetchone()
            if clash:
                continue
            db.execute(
                "UPDATE storage_shop_users SET referral_code = ? WHERE telegram_id = ?",
                (code, telegram_id),
            )
            db.commit()
            return code
    return ""


def apply_referral_from_start_payload(telegram_id: int, start_arg: str) -> None:
    raw = (start_arg or "").strip()
    if not raw:
        return
    code = ""
    if raw.lower().startswith("ref_"):
        code = raw[4:].strip().upper()
    elif raw.lower().startswith("ref"):
        code = raw[3:].strip().upper()
    if not code or len(code) > 16:
        return
    ensure_user(telegram_id)
    with sqlite3.connect(path_to_db) as db:
        ref_row = db.execute(
            "SELECT telegram_id FROM storage_shop_users WHERE upper(referral_code) = ? AND telegram_id != ?",
            (code, telegram_id),
        ).fetchone()
        if not ref_row:
            return
        referrer_id = int(ref_row[0])
        row = db.execute(
            "SELECT referred_by FROM storage_shop_users WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
        if row and int(row[0] or 0) != 0:
            return
        db.execute(
            "UPDATE storage_shop_users SET referred_by = ? WHERE telegram_id = ? AND (referred_by IS NULL OR referred_by = 0)",
            (referrer_id, telegram_id),
        )
        db.commit()


def apply_referral_bonuses_after_first_order(user_id: int) -> tuple[int, int]:
    """Начисляет бонусы при первом заказе по рефералке. Возвращает (бонус пригласившему, бонус новичку)."""
    if get_shop_setting("referral_program_enabled", "1") != "1":
        return 0, 0
    inviter_bonus = max(0, int(get_shop_setting("referral_bonus_inviter", "50") or 0))
    referee_bonus = max(0, int(get_shop_setting("referral_bonus_referee", "25") or 0))
    if inviter_bonus <= 0 and referee_bonus <= 0:
        return 0, 0
    with sqlite3.connect(path_to_db) as db:
        row = db.execute(
            "SELECT referred_by, referral_rewarded FROM storage_shop_users WHERE telegram_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return 0, 0
        referred_by = int(row[0] or 0)
        rewarded = int(row[1] or 0)
        if rewarded or referred_by <= 0 or referred_by == int(user_id):
            return 0, 0
        db.execute(
            "UPDATE storage_shop_users SET bonus = MAX(0, COALESCE(bonus, 0) + ?) WHERE telegram_id = ?",
            (inviter_bonus, referred_by),
        )
        db.execute(
            "UPDATE storage_shop_users SET bonus = MAX(0, COALESCE(bonus, 0) + ?) WHERE telegram_id = ?",
            (referee_bonus, user_id),
        )
        db.execute(
            "UPDATE storage_shop_users SET referral_rewarded = 1 WHERE telegram_id = ?",
            (user_id,),
        )
        db.commit()
    return inviter_bonus, referee_bonus


def save_product_rating(order_id: str, user_id: int, product_id: int, rating: int, comment: str = "") -> bool:
    """Save rating. Returns True if saved, False if already rated."""
    try:
        with sqlite3.connect(path_to_db) as db:
            db.execute(
                """
                INSERT OR IGNORE INTO storage_product_ratings(order_id, user_id, product_id, rating, created_at, comment)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (order_id, user_id, product_id, rating, _now(), (comment or "")[:2000]),
            )
            ok = db.total_changes > 0
            db.commit()
            return ok
    except Exception:
        return False


def update_product_rating_comment(order_id: str, product_id: int, comment: str) -> None:
    text = (comment or "").strip()
    if text == "—" or text == "-":
        text = ""
    text = text[:2000]
    with sqlite3.connect(path_to_db) as db:
        db.execute(
            "UPDATE storage_product_ratings SET comment = ? WHERE order_id = ? AND product_id = ?",
            (text, order_id, product_id),
        )
        db.commit()


def list_product_review_snippets(product_id: int, *, limit: int = 4) -> list[dict[str, Any]]:
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(
            """
            SELECT rating, comment, created_at
            FROM storage_product_ratings
            WHERE product_id = ? AND LENGTH(TRIM(comment)) > 0
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (product_id, limit),
        ).fetchall()
    return [{"rating": int(r[0]), "comment": (r[1] or "").strip(), "created_at": r[2] or ""} for r in rows]


def get_product_rating(product_id: int) -> dict[str, Any]:
    """Returns {avg: float, count: int}."""
    with sqlite3.connect(path_to_db) as db:
        row = db.execute(
            "SELECT AVG(rating), COUNT(*) FROM storage_product_ratings WHERE product_id = ?",
            (product_id,),
        ).fetchone()
    avg = round(float(row[0]), 1) if row and row[0] is not None else 0.0
    count = int(row[1]) if row else 0
    return {"avg": avg, "count": count}


def is_admin_user(telegram_id: int) -> bool:
    profile = get_user_profile(telegram_id)
    return profile["role"] in {"owner", "admin", "manager"}


def is_privileged_admin(telegram_id: int) -> bool:
    """Полный доступ: владелец или админ (не менеджер)."""
    profile = get_user_profile(telegram_id)
    return profile["role"] in {"owner", "admin"}


def is_owner_user(telegram_id: int) -> bool:
    profile = get_user_profile(telegram_id)
    return profile["role"] == "owner"


def get_admin_ids() -> list[int]:
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(
            """
            SELECT telegram_id FROM storage_shop_users
            WHERE role IN ('owner', 'admin', 'manager')
            ORDER BY CASE role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, created_at ASC
            """
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
    if profile["role"] not in {"owner", "admin", "manager"}:
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
    if role not in {"owner", "admin", "manager", "user"}:
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
            WHERE role IN ('owner', 'admin', 'manager')
            ORDER BY CASE role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, created_at DESC
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


def _search_tokens(search: str | None) -> list[str]:
    raw = (search or "").strip().lower()
    if not raw:
        return []
    parts = re.findall(r"[\w\d\u0400-\u04FF]{2,}", raw)
    if parts:
        return parts[:12]
    return [raw[:80]]


def _fuzzy_token_word_score(token: str, word: str) -> float:
    if len(word) < 2:
        return 0.0
    if token == word:
        return 3.0
    if len(token) >= 3 and (token in word or word in token):
        return 2.2
    r = SequenceMatcher(None, token, word).ratio()
    return r * 2.5 if r >= 0.68 else 0.0


def _fuzzy_product_score(
    name: str,
    description: str,
    brand: str,
    category_name: str,
    tokens: list[str],
) -> float:
    hay = f"{name} {description} {brand} {category_name}".lower()
    words = re.findall(r"[\w\d\u0400-\u04FF]+", hay)
    total = 0.0
    for t in tokens:
        if t in hay:
            total += 3.0
            continue
        best = 0.0
        for w in words:
            best = max(best, _fuzzy_token_word_score(t, w))
        total += best
    return total


def _list_products_fuzzy_paginated(
    *,
    category_id: int | None,
    only_available: bool | None,
    min_price: int | None,
    max_price: int | None,
    brand: str | None,
    tokens: list[str],
    page: int,
    per_page: int,
) -> tuple[list[dict[str, Any]], int]:
    sql, params = _build_products_where(
        category_id=category_id,
        search=None,
        only_available=only_available,
        min_price=min_price,
        max_price=max_price,
        brand=brand,
    )
    sql += " ORDER BY p.id DESC"
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(sql, params).fetchall()

    scored: list[tuple[float, tuple[Any, ...]]] = []
    for row in rows:
        sc = _fuzzy_product_score(
            str(row[1]),
            str(row[2] or ""),
            str(row[7] or ""),
            str(row[8] or ""),
            tokens,
        )
        if sc > 0:
            scored.append((sc, row))

    scored.sort(key=lambda x: (-x[0], -int(x[1][0])))
    total = len(scored)
    page = max(1, int(page))
    per_page = max(1, int(per_page))
    start = (page - 1) * per_page
    chunk = scored[start : start + per_page]

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
        for _, row in chunk
    ]
    return items, total


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
        tokens = _search_tokens(search)
        if tokens:
            or_parts: list[str] = []
            for t in tokens:
                needle = f"%{t}%"
                or_parts.append(
                    "(LOWER(p.name) LIKE ? OR LOWER(COALESCE(p.description, '')) LIKE ? OR "
                    "LOWER(COALESCE(p.brand, '')) LIKE ? OR LOWER(COALESCE(c.name, '')) LIKE ?)"
                )
                params.extend([needle, needle, needle, needle])
            sql += " AND (" + " OR ".join(or_parts) + ")"
        else:
            needle = f"%{search.strip().lower()}%"
            sql += " AND (LOWER(p.name) LIKE ? OR LOWER(COALESCE(p.description, '')) LIKE ? OR LOWER(COALESCE(p.brand, '')) LIKE ? OR LOWER(COALESCE(c.name, '')) LIKE ?)"
            params.extend([needle, needle, needle, needle])
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
    tokens = _search_tokens(search) if search else []

    sql += " ORDER BY p.id DESC LIMIT ? OFFSET ?"

    with sqlite3.connect(path_to_db) as db:
        total = int(db.execute(count_sql, params).fetchone()[0])
        rows = db.execute(sql, [*params, per_page, offset]).fetchall()

    if search and tokens and total == 0:
        return _list_products_fuzzy_paginated(
            category_id=category_id,
            only_available=only_available,
            min_price=min_price,
            max_price=max_price,
            brand=brand,
            tokens=tokens,
            page=page,
            per_page=per_page,
        )

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

    touch_cart_activity(user_id)
    return True, "🛒 Добавлено в корзину"


def remove_from_cart(user_id: int, product_id: int) -> None:
    with sqlite3.connect(path_to_db) as db:
        db.execute("DELETE FROM storage_shop_cart WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        db.commit()
    touch_cart_activity(user_id)
    if not get_cart(user_id):
        reset_cart_reminder_state(user_id)


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

    touch_cart_activity(user_id)
    if not get_cart(user_id):
        reset_cart_reminder_state(user_id)
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
    reset_cart_reminder_state(user_id)


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


def record_product_view(user_id: int, product_id: int) -> None:
    with sqlite3.connect(path_to_db) as db:
        db.execute(
            """
            INSERT INTO storage_shop_product_views(user_id, product_id, viewed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, product_id) DO UPDATE SET viewed_at = excluded.viewed_at
            """,
            (user_id, product_id, _now()),
        )
        db.commit()


def list_recent_views(user_id: int, *, limit: int = 12) -> list[dict[str, Any]]:
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(
            """
            SELECT v.product_id, p.name, p.price, p.stock
            FROM storage_shop_product_views v
            JOIN storage_shop_products p ON p.id = v.product_id
            WHERE v.user_id = ?
            ORDER BY datetime(v.viewed_at) DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [
        {"id": int(r[0]), "name": r[1], "price": int(r[2]), "stock": int(r[3])}
        for r in rows
    ]


def wishlist_user_ids_for_product(product_id: int) -> list[int]:
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(
            "SELECT user_id FROM storage_shop_wishlist WHERE product_id = ?",
            (product_id,),
        ).fetchall()
    return [int(r[0]) for r in rows if r and r[0]]


def set_user_applied_promo(user_id: int, code: str) -> None:
    c = (code or "").strip().upper()
    if not c:
        clear_user_applied_promo(user_id)
        return
    with sqlite3.connect(path_to_db) as db:
        db.execute(
            "INSERT INTO storage_shop_user_promo(user_id, code) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET code = excluded.code",
            (user_id, c),
        )
        db.commit()


def get_user_applied_promo(user_id: int) -> str:
    with sqlite3.connect(path_to_db) as db:
        row = db.execute(
            "SELECT code FROM storage_shop_user_promo WHERE user_id = ?", (user_id,)
        ).fetchone()
    return str(row[0]).strip() if row and row[0] else ""


def clear_user_applied_promo(user_id: int) -> None:
    with sqlite3.connect(path_to_db) as db:
        db.execute("DELETE FROM storage_shop_user_promo WHERE user_id = ?", (user_id,))
        db.commit()


def calc_promo_discount(code: str, subtotal: int, user_id: int | None = None) -> tuple[int, str]:
    """Возвращает (скидка_грн, сообщение_ошибки). При успехе сообщение пустое."""
    raw = (code or "").strip().upper()
    if not raw:
        return 0, ""
    if subtotal < 1:
        return 0, "Корзина пустая"
    with sqlite3.connect(path_to_db) as db:
        row = db.execute(
            """
            SELECT kind, value, max_uses, used_count, active, valid_until, target_user_id
            FROM storage_shop_promocodes WHERE upper(code) = ?
            """,
            (raw,),
        ).fetchone()
    if not row:
        return 0, "Промокод не найден"
    kind, value, max_uses, used_count, active, valid_until, target_user_id = (
        str(row[0] or "").lower(),
        int(row[1]),
        int(row[2]),
        int(row[3]),
        int(row[4]),
        str(row[5] or "").strip(),
        int(row[6]) if row[6] else 0,
    )
    if not active:
        return 0, "Промокод неактивен"
    if valid_until:
        try:
            if datetime.datetime.fromisoformat(valid_until) < datetime.datetime.now():
                return 0, "Срок промокода истёк"
        except ValueError:
            pass
    if max_uses >= 0 and used_count >= max_uses:
        return 0, "Лимит активаций исчерпан"
    if target_user_id > 0 and (user_id is None or int(user_id) != target_user_id):
        return 0, "Промокод предназначен для другого пользователя"
    value = max(0, value)
    if kind == "percent":
        off = (subtotal * value) // 100
    elif kind == "fixed":
        off = value
    else:
        return 0, "Некорректный тип скидки"
    off = max(0, min(subtotal - 1, off))
    return off, ""


def promo_discount_for_user_cart(user_id: int) -> tuple[int, str, str]:
    """Скидка по сохранённому промокоду пользователя. (amount, err, code)"""
    code = get_user_applied_promo(user_id)
    if not code:
        return 0, "", ""
    sub = cart_total(user_id)
    off, err = calc_promo_discount(code, sub, user_id=user_id)
    if err:
        return 0, err, code
    return off, "", code


def create_promocode(
    code: str,
    kind: str,
    value: int,
    *,
    max_uses: int = -1,
    valid_until: str = "",
    target_user_id: int = 0,
) -> tuple[bool, str]:
    raw = (code or "").strip().upper()
    k = (kind or "").strip().lower()
    if not raw or len(raw) > 40:
        return False, "Некорректный код"
    if k not in {"percent", "fixed"}:
        return False, "Тип: percent или fixed"
    if value < 0 or (k == "percent" and value > 90):
        return False, "Некорректное значение"
    if int(target_user_id) < 0:
        return False, "Некорректный user_id"
    try:
        with sqlite3.connect(path_to_db) as db:
            db.execute(
                """
                INSERT INTO storage_shop_promocodes(code, kind, value, max_uses, used_count, active, valid_until, target_user_id)
                VALUES (?, ?, ?, ?, 0, 1, ?, ?)
                """,
                (raw, k, int(value), int(max_uses), valid_until or "", int(target_user_id)),
            )
            db.commit()
        return True, f"Промокод {raw} создан"
    except Exception:
        return False, "Такой код уже есть"


def list_promocodes() -> list[dict[str, Any]]:
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(
            """
            SELECT id, code, kind, value, max_uses, used_count, active, valid_until, target_user_id
            FROM storage_shop_promocodes ORDER BY id DESC
            """
        ).fetchall()
    return [
        {
            "id": int(r[0]),
            "code": r[1],
            "kind": r[2],
            "value": int(r[3]),
            "max_uses": int(r[4]),
            "used_count": int(r[5]),
            "active": bool(r[6]),
            "valid_until": r[7] or "",
            "target_user_id": int(r[8]) if r[8] else 0,
        }
        for r in rows
    ]


def delete_promocode(code: str) -> bool:
    raw = (code or "").strip().upper()
    if not raw:
        return False
    with sqlite3.connect(path_to_db) as db:
        cur = db.execute("DELETE FROM storage_shop_promocodes WHERE upper(code) = ?", (raw,))
        db.commit()
        return cur.rowcount > 0


def toggle_promocode(code: str) -> bool:
    raw = (code or "").strip().upper()
    with sqlite3.connect(path_to_db) as db:
        row = db.execute(
            "SELECT active FROM storage_shop_promocodes WHERE upper(code) = ?", (raw,)
        ).fetchone()
        if not row:
            return False
        new_v = 0 if int(row[0]) else 1
        db.execute(
            "UPDATE storage_shop_promocodes SET active = ? WHERE upper(code) = ?",
            (new_v, raw),
        )
        db.commit()
        return True


def delete_promocode_id(row_id: int) -> bool:
    if row_id < 1:
        return False
    with sqlite3.connect(path_to_db) as db:
        cur = db.execute("DELETE FROM storage_shop_promocodes WHERE id = ?", (row_id,))
        db.commit()
        return cur.rowcount > 0


def toggle_promocode_id(row_id: int) -> bool:
    if row_id < 1:
        return False
    with sqlite3.connect(path_to_db) as db:
        row = db.execute("SELECT active FROM storage_shop_promocodes WHERE id = ?", (row_id,)).fetchone()
        if not row:
            return False
        new_v = 0 if int(row[0]) else 1
        db.execute("UPDATE storage_shop_promocodes SET active = ? WHERE id = ?", (new_v, row_id))
        db.commit()
        return True


def is_user_status_notification_enabled() -> bool:
    return get_shop_setting("notif_user_status_enabled", "1") == "1"


def set_user_status_notification_enabled(enabled: bool) -> None:
    set_shop_setting("notif_user_status_enabled", "1" if enabled else "0")


def export_orders_csv(limit: int = 2000) -> str:
    """UTF-8 CSV для Excel (разделитель ;)."""
    with sqlite3.connect(path_to_db) as db:
        rows = db.execute(
            """
            SELECT id, user_id, total_price, status, delivery, payment, customer_name,
                   customer_phone, customer_address, created_at, promo_code
            FROM storage_shop_orders
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    lines = ["order_id;user_id;total;status;delivery;payment;name;phone;address;created_at;promo_code"]
    for r in rows:
        def esc(x: Any) -> str:
            s = str(x if x is not None else "").replace('"', '""')
            if ";" in s or "\n" in s:
                return f'"{s}"'
            return s

        lines.append(
            ";".join(esc(v) for v in r),
        )
    return "\n".join(lines)


def get_analytics_extended() -> dict[str, Any]:
    now = datetime.datetime.now()
    week_start = (now - datetime.timedelta(days=7)).replace(microsecond=0).isoformat(sep=" ")
    with sqlite3.connect(path_to_db) as db:
        top_sales = db.execute(
            """
            SELECT i.title, SUM(i.quantity) AS q, SUM(i.quantity * i.price) AS rev
            FROM storage_shop_order_items i
            JOIN storage_shop_orders o ON o.id = i.order_id
            WHERE datetime(o.created_at) >= datetime(?)
            GROUP BY i.product_id, i.title
            ORDER BY q DESC
            LIMIT 8
            """,
            (week_start,),
        ).fetchall()
        top_views = db.execute(
            """
            SELECT p.name, COUNT(*) AS c
            FROM storage_shop_product_views v
            JOIN storage_shop_products p ON p.id = v.product_id
            GROUP BY v.product_id, p.name
            ORDER BY c DESC
            LIMIT 8
            """,
        ).fetchall()
        promo_used = db.execute(
            "SELECT COUNT(*) FROM storage_shop_orders WHERE trim(promo_code) != ''"
        ).fetchone()[0]
    return {
        "top_sales": [(str(t[0]), int(t[1]), int(t[2])) for t in top_sales],
        "top_views": [(str(t[0]), int(t[1])) for t in top_views],
        "orders_with_promo": int(promo_used or 0),
    }


def create_order_from_cart(
    user_id: int,
    *,
    name: str,
    phone: str,
    address: str,
    delivery: str,
    payment: str,
    discount: int = 0,
    promo_discount: int = 0,
    promo_code: str = "",
) -> tuple[bool, str]:
    cart = get_cart(user_id)
    if not cart:
        return False, "Корзина пустая"

    subtotal = sum(item["sum"] for item in cart)
    promo_off = max(0, int(promo_discount))
    after_promo = max(1, subtotal - promo_off)
    bonus_off = max(0, int(discount))
    total = max(1, after_promo - bonus_off)
    promo_tag = (promo_code or "").strip().upper()[:64]

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
                    customer_name, customer_phone, customer_address, created_at, promo_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (order_id, user_id, total, "Новый", delivery, payment, name, phone, address, _now(), promo_tag),
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
            if promo_tag and promo_off > 0:
                db.execute(
                    "UPDATE storage_shop_promocodes SET used_count = used_count + 1 WHERE upper(code) = ? AND (target_user_id = 0 OR target_user_id = ?)",
                    (promo_tag, int(user_id)),
                )
            db.commit()
        except Exception:
            db.rollback()
            return False, "Не удалось оформить заказ"

    update_user_contacts(user_id, name=name, phone=phone, address=address)
    clear_user_applied_promo(user_id)
    reset_cart_reminder_state(user_id)
    apply_referral_bonuses_after_first_order(user_id)
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
            "SELECT title, price, quantity, product_id FROM storage_shop_order_items WHERE order_id = ?",
            (order_id,),
        ).fetchall()

    return [{"title": row[0], "price": int(row[1]), "quantity": int(row[2]), "product_id": int(row[3])} for row in rows]


def get_order(order_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(path_to_db) as db:
        row = db.execute(
            """
            SELECT id, user_id, total_price, status, delivery, payment,
                   customer_name, customer_phone, customer_address, created_at,
                     receipt_file_id, receipt_file_type, receipt_sent_at,
                     receipt_review_status, receipt_reviewed_at, promo_code
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
        "promo_code": row[15] or "",
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


def export_catalog() -> dict[str, Any]:
    """Экспортирует все категории и товары в словарь для сериализации в JSON."""
    categories = list_categories()
    result: list[dict[str, Any]] = []
    for cat in categories:
        products_page, total = list_products_paginated(
            category_id=cat["id"], only_available=None, per_page=10000
        )
        result.append(
            {
                "name": cat["name"],
                "products": [
                    {
                        "name": p["name"],
                        "description": p["description"],
                        "price": p["price"],
                        "stock": p["stock"],
                        "brand": p["brand"],
                        "photo": p["photo"],
                    }
                    for p in products_page
                ],
            }
        )
    return {"version": 1, "categories": result}


def import_catalog(data: dict[str, Any]) -> tuple[int, int]:
    """Импортирует каталог из словаря.
    Возвращает (кол-во категорий, кол-во товаров).
    Существующие категории не дублируются; товары добавляются новые."""
    cats_count = 0
    prods_count = 0
    for cat_data in data.get("categories", []):
        cat_name = str(cat_data.get("name", "")).strip()
        if not cat_name:
            continue
        cat_id = get_or_create_category(cat_name)
        cats_count += 1
        for prod in cat_data.get("products", []):
            name = str(prod.get("name", "")).strip()
            if not name:
                continue
            create_product(
                name=name,
                description=str(prod.get("description", "")),
                price=int(prod.get("price", 0)),
                stock=int(prod.get("stock", 0)),
                category_id=cat_id,
                photo=str(prod.get("photo", "")),
                brand=str(prod.get("brand", "")),
            )
            prods_count += 1
    return cats_count, prods_count


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


def get_shop_stats_full() -> dict[str, Any]:
    """Расширенная статистика магазина по периодам."""
    now = datetime.datetime.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(sep=" ")
    week_start = (now - datetime.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(sep=" ")
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat(sep=" ")

    with sqlite3.connect(path_to_db) as db:
        # Товары
        total_products = db.execute("SELECT COUNT(*) FROM storage_shop_products").fetchone()[0]
        in_stock = db.execute("SELECT COUNT(*) FROM storage_shop_products WHERE stock > 0").fetchone()[0]
        out_of_stock = db.execute("SELECT COUNT(*) FROM storage_shop_products WHERE stock <= 0").fetchone()[0]
        total_units = db.execute("SELECT COALESCE(SUM(stock), 0) FROM storage_shop_products").fetchone()[0]
        categories = db.execute("SELECT COUNT(*) FROM storage_shop_categories").fetchone()[0]

        # Клиенты
        customers = db.execute("SELECT COUNT(*) FROM storage_shop_users WHERE role='user'").fetchone()[0]

        # Заказы за день
        orders_day = db.execute("SELECT COUNT(*) FROM storage_shop_orders WHERE created_at >= ?", (day_start,)).fetchone()[0]
        revenue_day = db.execute("SELECT COALESCE(SUM(total_price),0) FROM storage_shop_orders WHERE created_at >= ?", (day_start,)).fetchone()[0]
        sold_day = db.execute(
            "SELECT COALESCE(SUM(i.quantity),0) FROM storage_shop_order_items i "
            "JOIN storage_shop_orders o ON o.id = i.order_id WHERE o.created_at >= ?", (day_start,)
        ).fetchone()[0]

        # Заказы за неделю
        orders_week = db.execute("SELECT COUNT(*) FROM storage_shop_orders WHERE created_at >= ?", (week_start,)).fetchone()[0]
        revenue_week = db.execute("SELECT COALESCE(SUM(total_price),0) FROM storage_shop_orders WHERE created_at >= ?", (week_start,)).fetchone()[0]
        sold_week = db.execute(
            "SELECT COALESCE(SUM(i.quantity),0) FROM storage_shop_order_items i "
            "JOIN storage_shop_orders o ON o.id = i.order_id WHERE o.created_at >= ?", (week_start,)
        ).fetchone()[0]

        # Заказы за месяц
        orders_month = db.execute("SELECT COUNT(*) FROM storage_shop_orders WHERE created_at >= ?", (month_start,)).fetchone()[0]
        revenue_month = db.execute("SELECT COALESCE(SUM(total_price),0) FROM storage_shop_orders WHERE created_at >= ?", (month_start,)).fetchone()[0]
        sold_month = db.execute(
            "SELECT COALESCE(SUM(i.quantity),0) FROM storage_shop_order_items i "
            "JOIN storage_shop_orders o ON o.id = i.order_id WHERE o.created_at >= ?", (month_start,)
        ).fetchone()[0]

        # Всё время
        orders_all = db.execute("SELECT COUNT(*) FROM storage_shop_orders").fetchone()[0]
        revenue_all = db.execute("SELECT COALESCE(SUM(total_price),0) FROM storage_shop_orders").fetchone()[0]
        sold_all = db.execute("SELECT COALESCE(SUM(quantity),0) FROM storage_shop_order_items").fetchone()[0]

        orders_new = db.execute("SELECT COUNT(*) FROM storage_shop_orders WHERE status='Новый'").fetchone()[0]
        orders_inwork = db.execute("SELECT COUNT(*) FROM storage_shop_orders WHERE status IN ('Оплачен', 'Отправлен')").fetchone()[0]
        orders_done = db.execute("SELECT COUNT(*) FROM storage_shop_orders WHERE status='Доставлен'").fetchone()[0]
        orders_cancel = db.execute("SELECT COUNT(*) FROM storage_shop_orders WHERE status='Отменен'").fetchone()[0]

    return {
        "total_products": int(total_products),
        "in_stock": int(in_stock),
        "out_of_stock": int(out_of_stock),
        "total_units": int(total_units),
        "categories": int(categories),
        "customers": int(customers),
        "orders_day": int(orders_day), "revenue_day": int(revenue_day), "sold_day": int(sold_day),
        "orders_week": int(orders_week), "revenue_week": int(revenue_week), "sold_week": int(sold_week),
        "orders_month": int(orders_month), "revenue_month": int(revenue_month), "sold_month": int(sold_month),
        "orders_all": int(orders_all), "revenue_all": int(revenue_all), "sold_all": int(sold_all),
        "orders_new": int(orders_new),
        "orders_inwork": int(orders_inwork),
        "orders_done": int(orders_done),
        "orders_cancel": int(orders_cancel),
    }

