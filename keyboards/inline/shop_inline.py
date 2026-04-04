from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _role_label(role: str) -> str:
    return {
        "owner": "👑 главный",
        "admin": "🛡 админ",
        "manager": "📋 менеджер",
        "user": "👤 клиент",
    }.get(role, role)


def back_menu_kb(target: str = "menu:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data=target)]]
    )


def back_admin_kb(target: str = "admin:shop") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data=target)]]
    )


def categories_kb(categories: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for category in categories:
        pair.append(InlineKeyboardButton(text=category["name"], callback_data=f"shop:cat:{category['id']}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)

    rows.append(
        [
            InlineKeyboardButton(text="🔎 Поиск", callback_data="shop:search"),
            InlineKeyboardButton(text="👁 Недавние", callback_data="menu:recent"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(text="❤️ Избранное", callback_data="menu:wishlist"),
            InlineKeyboardButton(text="🧺 Корзина", callback_data="menu:cart"),
        ]
    )
    rows.append([InlineKeyboardButton(text="⬅ В меню", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def catalog_kb(products: list[dict], *, page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{product['name']}",
                callback_data=f"shop:product:{product['id']}",
            )
        ]
        for product in products
    ]
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅", callback_data="shop:page:prev"))
    nav.append(InlineKeyboardButton(text=f"{page}/{max(1, total_pages)}", callback_data="shop:noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="➡", callback_data="shop:page:next"))
    rows.append(nav)

    rows.append(
        [
            InlineKeyboardButton(text="📂 Категории", callback_data="menu:catalog"),
            InlineKeyboardButton(text="❤️ Избранное", callback_data="menu:wishlist"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(text="🧺 Корзина", callback_data="menu:cart"),
            InlineKeyboardButton(text="⬅ В меню", callback_data="menu:main"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_kb(product_id: int, *, in_wishlist: bool, show_cart_button: bool = False, has_reviews: bool = False) -> InlineKeyboardMarkup:
    wishlist_text = "💔 Убрать из избранного" if in_wishlist else "❤️ В избранное"
    rows = [
        [
            InlineKeyboardButton(text="🧺 В корзину", callback_data=f"shop:add:{product_id}"),
            InlineKeyboardButton(text=wishlist_text, callback_data=f"shop:wishlist:toggle:{product_id}"),
        ]
    ]
    if show_cart_button:
        rows.append([InlineKeyboardButton(text="🛒 Моя корзина", callback_data="menu:cart")])
    if has_reviews:
        rows.append([InlineKeyboardButton(text="💬 Отзывы", callback_data=f"shop:reviews:{product_id}")])
    rows.append([InlineKeyboardButton(text="⬅ Каталог", callback_data="menu:catalog")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_kb(items: list[dict], *, has_promo: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        pid = item["position_id"]
        rows.append(
            [
                InlineKeyboardButton(text="➖", callback_data=f"shop:cart:dec:{pid}"),
                InlineKeyboardButton(text=f"{item['title']} x{item['quantity']}", callback_data="shop:noop"),
                InlineKeyboardButton(text="➕", callback_data=f"shop:cart:inc:{pid}"),
                InlineKeyboardButton(text="❌", callback_data=f"shop:cart:remove:{pid}"),
            ]
        )

    rows.append([InlineKeyboardButton(text="✅ Оформить заказ", callback_data="shop:checkout:start")])
    rows.append([InlineKeyboardButton(text="🏷 Промокод", callback_data="shop:cart:promo")])
    if has_promo:
        rows.append([InlineKeyboardButton(text="✕ Убрать промокод", callback_data="shop:cart:promo:clear")])
    rows.append(
        [
            InlineKeyboardButton(text="🗑 Очистить", callback_data="shop:cart:clear"),
            InlineKeyboardButton(text="⬅ В меню", callback_data="menu:main"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


_NEW_STATUSES = {"Новый"}
_INWORK_STATUSES = {"Оплачен", "Отправлен"}
_ARCHIVE_STATUSES = {"Доставлен", "Отменен"}


def orders_menu_kb(*, has_new: bool, has_inwork: bool, has_archive: bool, has_receipt_search: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_new:
        rows.append([InlineKeyboardButton(text="🔵 Новые", callback_data="menu:orders:new")])
    if has_inwork:
        rows.append([InlineKeyboardButton(text="🔄 В работе", callback_data="menu:orders:inwork")])
    if has_archive:
        rows.append([InlineKeyboardButton(text="📁 Архив", callback_data="menu:orders:archive")])
    if has_receipt_search:
        rows.append([InlineKeyboardButton(text="🧾 Поиск по чеку", callback_data="menu:orders:receipt:search")])
    rows.append([InlineKeyboardButton(text="⬅ В меню", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def orders_new_kb(orders: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"🔵 {order['order_id']} · {order['total']} грн",
                callback_data=f"shop:order:{order['order_id']}",
            )
        ]
        for order in orders
        if order.get("status_raw", "") in _NEW_STATUSES
    ]
    rows.append([InlineKeyboardButton(text="⬅ К заказам", callback_data="menu:orders")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def orders_inwork_kb(orders: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"🔄 {order['order_id']} · {order['total']} грн",
                callback_data=f"shop:order:{order['order_id']}",
            )
        ]
        for order in orders
        if order.get("status_raw", "") in _INWORK_STATUSES
    ]
    rows.append([InlineKeyboardButton(text="⬅ К заказам", callback_data="menu:orders")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def orders_archive_kb(orders: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"📁 {order['order_id']} · {order['total']} грн",
                callback_data=f"shop:order:{order['order_id']}",
            )
        ]
        for order in orders
        if order.get("status_raw", "") in _ARCHIVE_STATUSES
    ]
    rows.append([InlineKeyboardButton(text="⬅ К заказам", callback_data="menu:orders")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def orders_list_kb(orders: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"📦 {order['order_id']} · {order['total']} грн · {order['status']}",
                callback_data=f"shop:order:{order['order_id']}",
            )
        ]
        for order in orders
    ]
    rows.append([InlineKeyboardButton(text="⬅ К заказам", callback_data="menu:orders")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_detail_kb(order_id: str, *, back_target: str, can_send_receipt: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_send_receipt:
        rows.append([InlineKeyboardButton(text="🧾 Отправить чек", callback_data=f"shop:receipt:start:{order_id}")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def wishlist_kb(products: list[dict], *, page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{'✅' if product['stock'] > 0 else '❌'} {product['name']} | {product['price']} грн",
                callback_data=f"shop:product:{product['id']}",
            )
        ]
        for product in products
    ]

    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅", callback_data="shop:wishlist:page:prev"))
    nav.append(InlineKeyboardButton(text=f"{page}/{max(1, total_pages)}", callback_data="shop:noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="➡", callback_data="shop:wishlist:page:next"))
    rows.append(nav)

    rows.append(
        [
            InlineKeyboardButton(text="📂 Категории", callback_data="menu:catalog"),
            InlineKeyboardButton(text="⬅ В меню", callback_data="menu:main"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_shop_kb(can_manage_admins: bool = False, *, full_access: bool = True) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🛍 Каталог · заказы · чеки", callback_data="admin:section:catalog")],
        [InlineKeyboardButton(text="💳 Оплата · реквизиты · доставка", callback_data="admin:section:payments")],
        [InlineKeyboardButton(text="🛟 Поддержка · тикеты клиентов", callback_data="admin:support_tickets")],
    ]
    if full_access:
        rows.append([InlineKeyboardButton(text="📦 Файлы · CSV заказов · JSON каталога", callback_data="admin:section:io")])
        rows.append([InlineKeyboardButton(text="👨‍💼 Команда · рассылка · промокоды", callback_data="admin:section:team")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_section_catalog_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Товар · новая позиция", callback_data="admin:product:add"),
                InlineKeyboardButton(text="📦 Список · редактирование", callback_data="admin:product:list"),
            ],
            [
                InlineKeyboardButton(text="🧾 Заказы · статусы", callback_data="admin:orders"),
                InlineKeyboardButton(text="🗂 Категории · структура", callback_data="admin:categories"),
            ],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="admin:shop")],
        ]
    )


def admin_section_appearance_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📝 /start · приветствие · фото", callback_data="admin:welcome:edit")],
        [InlineKeyboardButton(text="🏠 Меню · текст и картинка", callback_data="admin:main_menu:edit")],
    ]
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="admin:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_section_payments_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚙ Оплата · методы и реквизиты", callback_data="admin:settings:payments")],
            [InlineKeyboardButton(text="🚚 Доставка · НП · город · самовывоз", callback_data="admin:delivery:settings")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="admin:shop")],
        ]
    )


def admin_section_insights_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📰 Бот · ID · цифры", callback_data="admin:bot_info"),
                InlineKeyboardButton(text="📊 Сводка · 7 дней", callback_data="admin:analytics"),
            ],
            [
                InlineKeyboardButton(text="📈 Статистика · периоды", callback_data="admin:stats"),
                InlineKeyboardButton(text="👥 Клиенты · база", callback_data="admin:users:list:insights"),
            ],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="menu:admin")],
        ]
    )


def admin_section_io_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📥 CSV · заказы для Excel", callback_data="admin:orders:export"),
            ],
            [
                InlineKeyboardButton(text="📤 JSON · выгрузка каталога", callback_data="admin:catalog:export"),
                InlineKeyboardButton(text="📥 JSON · загрузка каталога", callback_data="admin:catalog:import"),
            ],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="admin:shop")],
        ]
    )


def admin_section_team_kb(*, can_manage_admins: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="📢 Рассылка · всем клиентам", callback_data="admin:broadcast"),
            InlineKeyboardButton(text="🏷 Промокоды · скидки", callback_data="admin:promos"),
        ],
        [InlineKeyboardButton(text="🛡 Админы · менеджеры", callback_data="admin:admins:list")],
    ]
    if can_manage_admins:
        rows.append([InlineKeyboardButton(text="➕ Новый администратор", callback_data="admin:admins:add")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="admin:shop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_products_kb(products: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{'✅' if product['stock'] > 0 else '❌'} {product['name']} · {product['price']} грн · {product['stock']} шт",
                callback_data=f"admin:product:view:{product['id']}",
            )
        ]
        for product in products
    ]
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="admin:section:catalog")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_product_actions_kb(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💰 Цена", callback_data=f"admin:product:price:{product_id}"),
                InlineKeyboardButton(text="📦 Остаток", callback_data=f"admin:product:stock:{product_id}"),
            ],
            [InlineKeyboardButton(text="📝 Описание", callback_data=f"admin:product:desc:{product_id}")],
            [InlineKeyboardButton(text="🖼 Фото", callback_data=f"admin:product:photo:{product_id}")],
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"admin:product:delete:{product_id}")],
            [InlineKeyboardButton(text="⬅ Список", callback_data="admin:product:list")],
        ]
    )


def checkout_delivery_kb(
    *,
    nova: bool = True,
    city: bool = True,
    pickup: bool = True,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if nova:
        rows.append([InlineKeyboardButton(text="🚚 Новая почта", callback_data="shop:delivery:nova")])
    if city:
        rows.append([InlineKeyboardButton(text="🚕 По городу", callback_data="shop:delivery:city")])
    if pickup:
        rows.append([InlineKeyboardButton(text="🏠 Самовывоз", callback_data="shop:delivery:pickup")])
    rows.append([InlineKeyboardButton(text="⬅ Корзина", callback_data="menu:cart")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def checkout_city_payment_kb() -> InlineKeyboardMarkup:
    """Для доставки 'По городу' — только оплата картой."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Банковская карта", callback_data="shop:pay:card")],
            [InlineKeyboardButton(text="⬅ Корзина", callback_data="menu:cart")],
        ]
    )


def checkout_payment_kb(payment_methods: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"shop:pay:{code}")]
        for code, label in payment_methods
    ]
    rows.append([InlineKeyboardButton(text="⬅ Корзина", callback_data="menu:cart")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def checkout_bonus_kb(bonus: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Использовать бонус ({bonus} грн)", callback_data="shop:bonus:use")],
            [InlineKeyboardButton(text="➡️ Продолжить без бонуса", callback_data="shop:bonus:skip")],
            [InlineKeyboardButton(text="⬅ Корзина", callback_data="menu:cart")],
        ]
    )


def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 Мои заказы", callback_data="menu:orders")],
            [InlineKeyboardButton(text="📞 Мой телефон", callback_data="profile:phone")],
            [InlineKeyboardButton(text="📍 Мой адрес", callback_data="profile:address")],
            [InlineKeyboardButton(text="⬅ В меню", callback_data="profile:back")],
        ]
    )


def admin_orders_kb(orders: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"📦 {order['order_id']} · {order['total']} грн · {order['status']}",
                callback_data=f"admin:order:view:{order['order_id']}",
            )
        ]
        for order in orders
    ]
    rows.append([InlineKeyboardButton(text="🧾 Поиск по чеку", callback_data="admin:orders:receipt:search")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="admin:orders")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_orders_menu_kb(*, has_new: bool, has_inwork: bool, has_archive: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_new:
        rows.append([InlineKeyboardButton(text="🔵 Новые", callback_data="admin:orders:new")])
    if has_inwork:
        rows.append([InlineKeyboardButton(text="🔄 В работе", callback_data="admin:orders:inwork")])
    if has_archive:
        rows.append([InlineKeyboardButton(text="📁 Архив", callback_data="admin:orders:archive")])
    rows.append([InlineKeyboardButton(text="🧾 Поиск по чеку", callback_data="admin:orders:receipt:search")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="admin:section:catalog")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def orders_receipt_filter_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏳ На проверке", callback_data="menu:orders:receipt:filter:pending")],
            [InlineKeyboardButton(text="✅ Подтвержден", callback_data="menu:orders:receipt:filter:approved")],
            [InlineKeyboardButton(text="❌ Отклонен", callback_data="menu:orders:receipt:filter:rejected")],
            [InlineKeyboardButton(text="📎 Есть чек", callback_data="menu:orders:receipt:filter:has")],
            [InlineKeyboardButton(text="🚫 Без чека", callback_data="menu:orders:receipt:filter:none")],
            [InlineKeyboardButton(text="⬅ Заказы", callback_data="menu:orders")],
        ]
    )


def admin_orders_receipt_filter_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏳ На проверке", callback_data="admin:orders:receipt:filter:pending")],
            [InlineKeyboardButton(text="✅ Подтвержден", callback_data="admin:orders:receipt:filter:approved")],
            [InlineKeyboardButton(text="❌ Отклонен", callback_data="admin:orders:receipt:filter:rejected")],
            [InlineKeyboardButton(text="📎 Есть чек", callback_data="admin:orders:receipt:filter:has")],
            [InlineKeyboardButton(text="🚫 Без чека", callback_data="admin:orders:receipt:filter:none")],
            [InlineKeyboardButton(text="⬅ Заказы", callback_data="admin:orders")],
        ]
    )


def admin_order_status_kb(
    order_id: str,
    user_id: int | None = None,
    *,
    receipt_pending: bool = False,
    has_receipt: bool = False,
    current_status_raw: str | None = None,
    payment_label: str | None = None,
) -> InlineKeyboardMarkup:
    status_buttons = {
        "paid": "✅ Оплачен",
        "shipped": "🚚 Отправлен",
        "done": "📦 Доставлен",
        "cancel": "❌ Отменен",
    }
    current_status_key = {
        "Оплачен": "paid",
        "Отправлен": "shipped",
        "Доставлен": "done",
        "Отменен": "cancel",
    }.get((current_status_raw or "").strip(), "")
    is_cod_payment = "налож" in (payment_label or "").strip().lower()

    rows: list[list[InlineKeyboardButton]] = []
    is_terminal_status = current_status_key in {"done", "cancel"}
    if not is_terminal_status:
        if current_status_key == "" and not is_cod_payment:
            rows.append([InlineKeyboardButton(text=status_buttons["paid"], callback_data=f"admin:order:status:{order_id}:paid")])

        shipping_row: list[InlineKeyboardButton] = []
        if current_status_key != "shipped":
            shipping_row.append(InlineKeyboardButton(text=status_buttons["shipped"], callback_data=f"admin:order:status:{order_id}:shipped"))
        if current_status_key != "done":
            shipping_row.append(InlineKeyboardButton(text=status_buttons["done"], callback_data=f"admin:order:status:{order_id}:done"))
        if shipping_row:
            rows.append(shipping_row)

        if current_status_key != "cancel":
            rows.append([InlineKeyboardButton(text=status_buttons["cancel"], callback_data=f"admin:order:status:{order_id}:cancel")])

    if receipt_pending:
        rows.append(
            [
                InlineKeyboardButton(text="✅ Подтвердить чек", callback_data=f"admin:order:receipt:{order_id}:approve"),
                InlineKeyboardButton(text="❌ Отклонить чек", callback_data=f"admin:order:receipt:{order_id}:reject"),
            ]
        )
    if has_receipt:
        rows.append([InlineKeyboardButton(text="🧾 Посмотреть чек", callback_data=f"admin:order:receipt:{order_id}:view")])
    if user_id is not None:
        rows.append([InlineKeyboardButton(text="✉️ Написать покупателю", callback_data=f"admin:order:msg:{order_id}")])
        rows.append([InlineKeyboardButton(text="👤 Карточка клиента", callback_data=f"admin:user:view:{user_id}")])
    rows.append([InlineKeyboardButton(text="⬅ Заказы", callback_data="admin:orders")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_people_kb(users: list[dict], *, back_target: str = "admin:shop", add_admin_button: bool = False, source: str = "") -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{user['name']} | {user['telegram_id']} | {_role_label(user['role'])}",
                callback_data=(
                    f"admin:user:view:{user['telegram_id']}:{source}" if source else f"admin:user:view:{user['telegram_id']}"
                ),
            )
        ]
        for user in users
    ]
    if add_admin_button:
        rows.append([InlineKeyboardButton(text="➕ Выдать админа", callback_data="admin:admins:add")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_user_actions_kb(
    user_id: int,
    *,
    is_admin: bool,
    is_owner: bool,
    is_manager: bool,
    can_manage_admins: bool,
    is_support: bool = False,
    back_target: str,
    source: str = "",
) -> InlineKeyboardMarkup:
    suffix = f":{source}" if source else ""
    rows = [
        [InlineKeyboardButton(text="✉️ Написать", callback_data=f"admin:user:msg:{user_id}{suffix}")],
        [InlineKeyboardButton(text="🛒 Покупки", callback_data=f"admin:user:orders:{user_id}{suffix}")],
        [InlineKeyboardButton(text="🎁 Выдать Бонус", callback_data=f"admin:user:bonus:{user_id}{suffix}")],
    ]
    if can_manage_admins and not is_owner and (is_admin or is_manager):
        if is_support:
            rows.append([InlineKeyboardButton(text="🛟 Убрать из техподдержки", callback_data=f"admin:user:support:disable:{user_id}{suffix}")])
        else:
            rows.append([InlineKeyboardButton(text="🛟 Назначить в техподдержку", callback_data=f"admin:user:support:enable:{user_id}{suffix}")])
        label = "➖ Убрать из админов" if is_admin else "➖ Снять менеджера"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"admin:user:demote:{user_id}{suffix}")])
    elif can_manage_admins and not is_owner and not is_admin and not is_manager:
        rows.append([InlineKeyboardButton(text="📋 Менеджер магазина", callback_data=f"admin:user:manager:{user_id}{suffix}")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_rating_kb(order_id: str, product_id: int) -> InlineKeyboardMarkup:
    stars = ["1 ⭐", "2 ⭐⭐", "3 ⭐⭐⭐", "4 ⭐⭐⭐⭐", "5 ⭐⭐⭐⭐⭐"]
    buttons = [
        InlineKeyboardButton(text=s, callback_data=f"shop:rate:{order_id}:{product_id}:{i+1}")
        for i, s in enumerate(stars)
    ]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="menu:orders")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_survey_kb(order_id: str, product_id: int) -> InlineKeyboardMarkup:
    """Клавиатура опроса при доставке: 5 кнопок со звездами по одной в строке."""
    rows = [
        [InlineKeyboardButton(text="⭐" * i, callback_data=f"shop:rate:{order_id}:{product_id}:{i}")]
        for i in range(5, 0, -1)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_delivery_settings_kb(nova: bool, city: bool, pickup: bool) -> InlineKeyboardMarkup:
    def _toggle_label(label: str, enabled: bool) -> str:
        return f"{'✅' if enabled else '❌'} {label}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_toggle_label("Новая почта", nova), callback_data="admin:delivery:toggle:nova")],
            [InlineKeyboardButton(text=_toggle_label("По городу", city), callback_data="admin:delivery:toggle:city")],
            [InlineKeyboardButton(text=_toggle_label("Самовывоз", pickup), callback_data="admin:delivery:toggle:pickup")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="admin:section:payments")],
        ]
    )


def admin_categories_kb(categories: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=category["name"], callback_data=f"admin:category:view:{category['id']}")
        ]
        for category in categories
    ]
    rows.append([InlineKeyboardButton(text="➕ Создать категорию", callback_data="admin:category:add")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="admin:section:catalog")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_product_category_kb(categories: list[dict]) -> InlineKeyboardMarkup:
    """Клавиатура выбора категории при добавлении товара."""
    rows = [
        [InlineKeyboardButton(text=cat["name"], callback_data=f"admin:product:catsel:{cat['id']}")]
        for cat in categories
    ]
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="admin:section:catalog")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_category_actions_kb(category_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Удалить категорию", callback_data=f"admin:category:delete:{category_id}")],
            [InlineKeyboardButton(text="⬅ Категории", callback_data="admin:categories")],
        ]
    )
