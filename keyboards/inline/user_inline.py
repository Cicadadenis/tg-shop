from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_inline_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="🛍 Каталог", callback_data="menu:catalog"),
            InlineKeyboardButton(text="🧺 Корзина", callback_data="menu:cart"),
        ],
        [
            InlineKeyboardButton(text="📦 Заказы", callback_data="menu:orders"),
            InlineKeyboardButton(text="❤️ Избранное", callback_data="menu:wishlist"),
        ],
        [
            InlineKeyboardButton(text="📱 Профиль", callback_data="menu:profile"),
            InlineKeyboardButton(text="ℹ FAQ", callback_data="menu:faq"),
        ],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="⚙ Админ меню", callback_data="menu:admin")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def account_categories_inline_kb(categories: list[tuple]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=str(category[1]), callback_data=f"category:{category[0]}")]
        for category in categories
    ]
    rows.append([InlineKeyboardButton(text="⬅ В меню", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


profile_actions_inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📦 Мои заказы", callback_data="menu:orders")],
        [InlineKeyboardButton(text="📞 Мой телефон", callback_data="profile:phone")],
        [InlineKeyboardButton(text="📍 Мой адрес", callback_data="profile:address")],
        [InlineKeyboardButton(text="⬅ В меню", callback_data="profile:back")],
    ]
)


admin_menu_inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Управление магазином", callback_data="admin:shop")],
        [InlineKeyboardButton(text="📰 Информация о боте", callback_data="admin:bot_info")],
        [
            InlineKeyboardButton(text="📝 Стартовое сообщение", callback_data="admin:welcome:edit"),
            InlineKeyboardButton(text="🛠 Тех.работы", callback_data="admin:maintenance:toggle"),
        ],
        [InlineKeyboardButton(text="⚙ Настройки", callback_data="admin:settings")],
        [InlineKeyboardButton(text="⬅ В меню", callback_data="menu:main")],
    ]
)


admin_settings_inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Шаблон: новый заказ", callback_data="admin:notif:new")],
        [InlineKeyboardButton(text="📦 Шаблон: статус клиенту", callback_data="admin:notif:status")],
        [InlineKeyboardButton(text="📢 Лог-чат заказов", callback_data="admin:notif:chat")],
        [InlineKeyboardButton(text="🗂 Бэкап БД", callback_data="admin:db:backup")],
        [InlineKeyboardButton(text="💵 Наложенный платеж вкл/выкл", callback_data="admin:pay:cod:toggle")],
        [InlineKeyboardButton(text="💳 Банковская карта", callback_data="admin:pay:card")],
        [InlineKeyboardButton(text=" Apple Pay", callback_data="admin:pay:applepay")],
        [InlineKeyboardButton(text="▶ Google Pay", callback_data="admin:pay:googlepay")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="menu:admin")],
    ]
)
