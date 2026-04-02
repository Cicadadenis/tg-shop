from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_inline_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    if is_admin:
        rows = [
            [
                InlineKeyboardButton(text="🛘 Каталог", callback_data="menu:catalog"),
                InlineKeyboardButton(text="🪺 Корзина", callback_data="menu:cart"),
            ],
            [
                InlineKeyboardButton(text="📦 Заказы", callback_data="menu:orders"),
                InlineKeyboardButton(text="📱 Профиль", callback_data="menu:profile"),
            ],
            [InlineKeyboardButton(text="⚙ Админ меню", callback_data="menu:admin")],
        ]
    else:
        rows = [
            [
                InlineKeyboardButton(text="🛘 Каталог", callback_data="menu:catalog"),
                InlineKeyboardButton(text="🪺 Корзина", callback_data="menu:cart"),
            ],
            [
                InlineKeyboardButton(text="📦 Заказы", callback_data="menu:orders"),
                InlineKeyboardButton(text="❤️ Избранное", callback_data="menu:wishlist"),
            ],
            [
                InlineKeyboardButton(text="📱 Профиль", callback_data="menu:profile"),
                InlineKeyboardButton(text="🛞 Тех. поддержка", callback_data="menu:support"),
            ],
        ]

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
        [InlineKeyboardButton(text="✏ Изменить данные", callback_data="profile:edit")],
        [InlineKeyboardButton(text="⬅ В меню", callback_data="profile:back")],
    ]
)


support_menu_inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать в поддержку", callback_data="support:start")],
        [InlineKeyboardButton(text="⬅ В меню", callback_data="menu:main")],
    ]
)


support_back_inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="⬅ К поддержке", callback_data="menu:support")]]
)

admin_reply_cancel_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="admin:support_tickets")]]
)


def admin_menu_inline_kb(maintenance_enabled: bool = False) -> InlineKeyboardMarkup:
    maintenance_indicator = "🔴" if maintenance_enabled else "🟢"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Управление магазином", callback_data="admin:shop")],
            [InlineKeyboardButton(text="📰 Информация о боте", callback_data="admin:bot_info")],
            [
                InlineKeyboardButton(text="📝 Приветствие", callback_data="admin:welcome:edit"),
                InlineKeyboardButton(text=f"🛠 Тех.работы {maintenance_indicator}", callback_data="admin:maintenance:toggle"),
            ],
            [InlineKeyboardButton(text="⚙ Настройки", callback_data="admin:settings")],
            [InlineKeyboardButton(text="🛟 Обращения в поддержку", callback_data="admin:support_tickets")],
            [InlineKeyboardButton(text="⬅ В меню", callback_data="menu:main")],
        ]
    )


def support_tickets_list_kb(tickets: list, *, show_closed: bool = False) -> InlineKeyboardMarkup:
    """Keyboard with one button per ticket."""
    rows = []
    for t in tickets:
        indicator = "🟢" if t["status"] == "active" else "🔴"
        name = t["first_name"] or t["username"] or "Клиент"
        preview = (t["message"][:25] + "…") if len(t["message"]) > 25 else t["message"]
        label = f"{indicator} #{t['id']} {name}: {preview}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"admin:ticket:{t['id']}")])
    if show_closed:
        rows.append([InlineKeyboardButton(text="🟢 Активные обращения", callback_data="admin:support_tickets")])
    else:
        rows.append([InlineKeyboardButton(text="📁 Завершенные", callback_data="admin:support_tickets:closed")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def support_ticket_view_kb(ticket_id: int, status: str) -> InlineKeyboardMarkup:
    """Keyboard for a single ticket view."""
    rows = [
        [InlineKeyboardButton(text="↩️ Ответить", callback_data=f"support:reply:{ticket_id}")],
    ]
    if status == "active":
        rows.append([InlineKeyboardButton(text="✅ Закрыть обращение", callback_data=f"admin:ticket:close:{ticket_id}")])
    back_target = "admin:support_tickets:closed" if status == "closed" else "admin:support_tickets"
    rows.append([InlineKeyboardButton(text="⬅ К списку", callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_settings_inline_kb(cod_enabled: bool = False, card_enabled: bool = False, applepay_enabled: bool = False, googlepay_enabled: bool = False) -> InlineKeyboardMarkup:
    cod_indicator = "🟢" if cod_enabled else "🔴"
    card_indicator = "🟢" if card_enabled else "🔴"
    applepay_indicator = "🟢" if applepay_enabled else "🔴"
    googlepay_indicator = "🟢" if googlepay_enabled else "🔴"
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Шаблон: новый заказ", callback_data="admin:notif:new")],
            [InlineKeyboardButton(text="📦 Шаблон: статус клиенту", callback_data="admin:notif:status")],
            [InlineKeyboardButton(text="📢 Лог-чат заказов", callback_data="admin:notif:chat")],
            [InlineKeyboardButton(text="🗂 Бэкап БД", callback_data="admin:db:backup")],
            [InlineKeyboardButton(text=f"💵 Наложенный платеж {cod_indicator}", callback_data="admin:pay:cod:toggle")],
            [InlineKeyboardButton(text=f"💳 Банковская карта {card_indicator}", callback_data="admin:pay:card")],
            [InlineKeyboardButton(text=f" Apple Pay {applepay_indicator}", callback_data="admin:pay:applepay")],
            [InlineKeyboardButton(text=f"▶ Google Pay {googlepay_indicator}", callback_data="admin:pay:googlepay")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="menu:admin")],
        ]
    )
