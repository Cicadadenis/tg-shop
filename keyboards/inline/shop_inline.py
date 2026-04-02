from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _role_label(role: str) -> str:
    return {
        "owner": "главный",
        "admin": "админ",
        "user": "клиент",
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
    rows.append(
        [
            InlineKeyboardButton(text="💸 Цена", callback_data="shop:filter:price"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(text="✅ В наличии", callback_data="shop:filter:stock"),
            InlineKeyboardButton(text="♻ Сброс", callback_data="shop:filter:reset"),
        ]
    )

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


def product_kb(product_id: int, *, in_wishlist: bool, show_cart_button: bool = False) -> InlineKeyboardMarkup:
    wishlist_text = "💔 Убрать из избранного" if in_wishlist else "❤️ В избранное"
    rows = [
        [
            InlineKeyboardButton(text="🧺 В корзину", callback_data=f"shop:add:{product_id}"),
            InlineKeyboardButton(text=wishlist_text, callback_data=f"shop:wishlist:toggle:{product_id}"),
        ]
    ]
    if show_cart_button:
        rows.append([InlineKeyboardButton(text="🛒 Моя корзина", callback_data="menu:cart")])
    rows.append([InlineKeyboardButton(text="⬅ Каталог", callback_data="menu:catalog")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_kb(items: list[dict]) -> InlineKeyboardMarkup:
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
                text=f"{order['order_id']} | {order['total']} грн | {order['status']}",
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
                text=f"{order['order_id']} | {order['total']} грн | {order['status']}",
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
                text=f"{order['order_id']} | {order['total']} грн | {order['status']}",
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
                text=f"{order['order_id']} | {order['total']} грн | {order['status']}",
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
                text=f"{product['name']} | {product['price']} грн | {product['stock']} шт",
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


def admin_shop_kb(can_manage_admins: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="➕ Добавить", callback_data="admin:product:add"),
            InlineKeyboardButton(text="📦 Товары", callback_data="admin:product:list"),
        ],
        [
            InlineKeyboardButton(text="🧾 Заказы", callback_data="admin:orders"),
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast"),
        ],
        [
            InlineKeyboardButton(text="🗂 Категории", callback_data="admin:categories"),
            InlineKeyboardButton(text="👥 Клиенты", callback_data="admin:users:list"),
        ],
        [InlineKeyboardButton(text="🛡 Админы", callback_data="admin:admins:list")],
    ]
    if can_manage_admins:
        rows.append([InlineKeyboardButton(text="➕ Выдать админа", callback_data="admin:admins:add")])
    rows.extend(
        [
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
            [InlineKeyboardButton(text="⬅ Админ меню", callback_data="menu:admin")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_products_kb(products: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{product['name']} | {product['price']} грн | {product['stock']} шт",
                callback_data=f"admin:product:view:{product['id']}",
            )
        ]
        for product in products
    ]
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="admin:shop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_product_actions_kb(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💰 Цена", callback_data=f"admin:product:price:{product_id}"),
                InlineKeyboardButton(text="📦 Остаток", callback_data=f"admin:product:stock:{product_id}"),
            ],
            [InlineKeyboardButton(text="🖼 Фото", callback_data=f"admin:product:photo:{product_id}")],
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"admin:product:delete:{product_id}")],
            [InlineKeyboardButton(text="⬅ Список", callback_data="admin:product:list")],
        ]
    )


def checkout_delivery_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚚 Новая почта", callback_data="shop:delivery:nova")],
            [InlineKeyboardButton(text="📦 Укрпочта", callback_data="shop:delivery:ukr")],
            [InlineKeyboardButton(text="🏠 Самовывоз", callback_data="shop:delivery:pickup")],
        ]
    )


def checkout_payment_kb(payment_methods: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"shop:pay:{code}")]
        for code, label in payment_methods
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
                text=f"{order['order_id']} | {order['total']} грн | {order['status']}",
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
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="admin:shop")])
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
    if current_status_key != "paid" and not is_cod_payment:
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


def admin_people_kb(users: list[dict], *, back_target: str = "admin:shop", add_admin_button: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{user['name']} | {user['telegram_id']} | {_role_label(user['role'])}",
                callback_data=f"admin:user:view:{user['telegram_id']}",
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
    can_manage_admins: bool,
    is_support: bool = False,
    back_target: str,
) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="✉️ Написать", callback_data=f"admin:user:msg:{user_id}")]]
    if can_manage_admins and is_admin and not is_owner:
        if is_support:
            rows.append([InlineKeyboardButton(text="🛟 Убрать из техподдержки", callback_data=f"admin:user:support:disable:{user_id}")])
        else:
            rows.append([InlineKeyboardButton(text="🛟 Назначить в техподдержку", callback_data=f"admin:user:support:enable:{user_id}")])
    if can_manage_admins and not is_owner:
        if is_admin:
            rows.append([InlineKeyboardButton(text="➖ Убрать из админов", callback_data=f"admin:user:demote:{user_id}")])
        else:
            rows.append([InlineKeyboardButton(text="➕ Сделать админом", callback_data=f"admin:user:promote:{user_id}")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_categories_kb(categories: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=category["name"], callback_data=f"admin:category:view:{category['id']}")
        ]
        for category in categories
    ]
    rows.append([InlineKeyboardButton(text="➕ Создать категорию", callback_data="admin:category:add")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="admin:shop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_product_category_kb(categories: list[dict]) -> InlineKeyboardMarkup:
    """Клавиатура выбора категории при добавлении товара."""
    rows = [
        [InlineKeyboardButton(text=cat["name"], callback_data=f"admin:product:catsel:{cat['id']}")]
        for cat in categories
    ]
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="admin:shop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_category_actions_kb(category_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Удалить категорию", callback_data=f"admin:category:delete:{category_id}")],
            [InlineKeyboardButton(text="⬅ Категории", callback_data="admin:categories")],
        ]
    )
