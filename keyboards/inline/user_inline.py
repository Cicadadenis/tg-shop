from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_inline_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    if is_admin:
        rows = [
            [
                InlineKeyboardButton(text="📂 Каталог", callback_data="menu:catalog"),
                InlineKeyboardButton(text="🧺 Корзина", callback_data="menu:cart"),
            ],
            [
                InlineKeyboardButton(text="📦 Заказы", callback_data="menu:orders"),
                InlineKeyboardButton(text="📱 Профиль", callback_data="menu:profile"),
            ],
            [InlineKeyboardButton(text="⚙️ Админ меню", callback_data="menu:admin")],
        ]
    else:
        rows = [
            [
                InlineKeyboardButton(text="📂 Каталог", callback_data="menu:catalog"),
                InlineKeyboardButton(text="🧺 Корзина", callback_data="menu:cart"),
            ],
            [
                InlineKeyboardButton(text="📦 Заказы", callback_data="menu:orders"),
                InlineKeyboardButton(text="📱 Профиль", callback_data="menu:profile"),
            ],
            [
                InlineKeyboardButton(text="❤️ Избранное", callback_data="menu:wishlist"),
                InlineKeyboardButton(text="💬 Поддержка", callback_data="menu:support"),
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
        [InlineKeyboardButton(text="📦 Заказы · история покупок", callback_data="menu:orders")],
        [InlineKeyboardButton(text="⬅ В меню · главный экран", callback_data="profile:back")],
    ]
)


support_menu_inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать · новое обращение", callback_data="support:start")],
        [InlineKeyboardButton(text="⬅ В меню · назад", callback_data="menu:main")],
    ]
)


support_back_inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="⬅ К поддержке", callback_data="menu:support")]]
)

admin_reply_cancel_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="admin:support_tickets")]]
)


def admin_menu_inline_kb(*, full_access: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🛒 Магазин · каталог · заказы · админка", callback_data="admin:shop")],
        [InlineKeyboardButton(text="📊 Сводка · бот · клиенты · метрики", callback_data="admin:section:insights")],
    ]
    rows.extend(
        [
            [InlineKeyboardButton(text="⚙ Настройки", callback_data="admin:settings")],
            [InlineKeyboardButton(text="⬅ В меню", callback_data="menu:main")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="admin:shop")])
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


def admin_settings_inline_kb(
    cod_enabled: bool = False,
    card_enabled: bool = False,
    applepay_enabled: bool = False,
    googlepay_enabled: bool = False,
    *,
    client_status_notif: bool = True,
    maintenance_enabled: bool = False,
) -> InlineKeyboardMarkup:
    maint_ind = "🟢 ВКЛ" if maintenance_enabled else "🔴 ВЫКЛ"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎨 Витрина · /start · главное меню", callback_data="admin:section:appearance")],
            [InlineKeyboardButton(text="🔔 Шаблоны · статусы · лог-чат", callback_data="admin:settings:notif")],
            [InlineKeyboardButton(text="🕐 Время работы", callback_data="admin:settings:business_hours")],
            [InlineKeyboardButton(text="🤝 Пригласи друга", callback_data="admin:settings:referral")],
            [InlineKeyboardButton(text=f"🛠 Техработы {maint_ind}", callback_data="admin:maintenance:toggle")],
            [InlineKeyboardButton(text="🗂 Сервис · бэкап базы", callback_data="admin:settings:service")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="menu:admin")],
        ]
    )


def admin_business_hours_kb(*, enabled: bool) -> InlineKeyboardMarkup:
    ind = "🟢" if enabled else "🔴"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{ind} Ограничение по времени", callback_data="admin:bhours:toggle")],
            [InlineKeyboardButton(text="🕐 Начало приёма", callback_data="admin:bhours:start")],
            [InlineKeyboardButton(text="🕙 Конец приёма", callback_data="admin:bhours:end")],
            [InlineKeyboardButton(text="⬅ Назад · настройки", callback_data="admin:settings")],
        ]
    )


def admin_referral_kb(*, enabled: bool, inviter: int, referee: int) -> InlineKeyboardMarkup:
    ind = "🟢 ВКЛ" if enabled else "🔴 ВЫКЛ"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{ind} Реферальная программа", callback_data="admin:referral:toggle")],
            [InlineKeyboardButton(text=f"🎁 Бонус пригласившему: {inviter} грн", callback_data="admin:referral:inviter")],
            [InlineKeyboardButton(text=f"🎁 Бонус новичку: {referee} грн", callback_data="admin:referral:referee")],
            [InlineKeyboardButton(text="⬅ Назад · настройки", callback_data="admin:settings")],
        ]
    )


def admin_settings_notifications_inline_kb(*, client_status_notif: bool = True) -> InlineKeyboardMarkup:
    status_indicator = "🟢" if client_status_notif else "🔴"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Админу · текст нового заказа", callback_data="admin:notif:new")],
            [InlineKeyboardButton(text="📦 Клиенту · шаблон статуса", callback_data="admin:notif:status")],
            [InlineKeyboardButton(text="✏️ Меню Telegram · описание /start", callback_data="admin:notif:start_cmd")],
            [InlineKeyboardButton(text=f"📬 Авто-статус клиенту {status_indicator}", callback_data="admin:notif:client_toggle")],
            [InlineKeyboardButton(text="📢 Лог-чат · дубли заказов", callback_data="admin:notif:chat")],
            [InlineKeyboardButton(text="⬅ Назад · все настройки", callback_data="admin:settings")],
        ]
    )


def admin_settings_payments_inline_kb(
    cod_enabled: bool = False,
    card_enabled: bool = False,
    applepay_enabled: bool = False,
    googlepay_enabled: bool = False,
) -> InlineKeyboardMarkup:
    cod_indicator = "🟢" if cod_enabled else "🔴"
    card_indicator = "🟢" if card_enabled else "🔴"
    applepay_indicator = "🟢" if applepay_enabled else "🔴"
    googlepay_indicator = "🟢" if googlepay_enabled else "🔴"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"💵 Наложенный платеж {cod_indicator}", callback_data="admin:pay:cod:toggle")],
            [InlineKeyboardButton(text=f"💳 Банковская карта {card_indicator}", callback_data="admin:pay:card")],
            [InlineKeyboardButton(text=f"🍏 Apple Pay {applepay_indicator}", callback_data="admin:pay:applepay")],
            [InlineKeyboardButton(text=f"▶ Google Pay {googlepay_indicator}", callback_data="admin:pay:googlepay")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="admin:section:payments")],
        ]
    )


def admin_settings_service_inline_kb(*, can_update_repo: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="💾 Бэкап · скачать SQLite", callback_data="admin:db:backup")],
    ]
    if can_update_repo:
        rows.append([InlineKeyboardButton(text="🔄 Обновить с Git", callback_data="admin:repo:update")])
    rows.append([InlineKeyboardButton(text="⬅ Назад · настройки", callback_data="admin:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_text_menus_kb(menus: dict) -> InlineKeyboardMarkup:
    """Клавиатура со списком текстовых меню"""
    rows = []
    for menu_id, menu_data in menus.items():
        rows.append([InlineKeyboardButton(text=f"📝 {menu_data['name']}", callback_data=f"admin:text_menu:{menu_id}")])
    rows.append([InlineKeyboardButton(text="➕ Создать меню", callback_data="admin:text_menu:new")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_text_menu_actions_kb(menu_id: str) -> InlineKeyboardMarkup:
    """Клавиатура с действиями для конкретного меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin:text_menu:edit:{menu_id}")],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:text_menu:delete:{menu_id}")],
            [InlineKeyboardButton(text="⬅ Назад к меню", callback_data="admin:text_menus")],
        ]
    )


def admin_text_menu_cancel_kb() -> InlineKeyboardMarkup:
    """Клавиатура для отмены создания/редактирования меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅ Отмена", callback_data="admin:text_menus")]]
    )
