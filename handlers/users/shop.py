from math import ceil
import io
import json
import re

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from keyboards.inline.shop_inline import (
    admin_categories_kb,
    admin_category_actions_kb,
    admin_product_category_kb,
    admin_people_kb,
    back_admin_kb,
    back_menu_kb,
    admin_delivery_settings_kb,
    admin_order_status_kb,
    admin_orders_receipt_filter_kb,
    admin_orders_menu_kb,
    admin_orders_kb,
    admin_product_actions_kb,
    admin_products_kb,
    admin_shop_kb,
    admin_user_actions_kb,
    cart_kb,
    catalog_kb,
    categories_kb,
    checkout_bonus_kb,
    checkout_city_payment_kb,
    checkout_delivery_kb,
    checkout_payment_kb,
    orders_archive_kb,
    orders_list_kb,
    orders_receipt_filter_kb,
    order_detail_kb,
    orders_inwork_kb,
    orders_menu_kb,
    orders_new_kb,
    product_kb,
    product_rating_kb,
    product_survey_kb,
    wishlist_kb,
)
from keyboards.inline.user_inline import main_menu_inline_kb, profile_actions_inline_kb, admin_menu_inline_kb
from utils.db_api.shop import (
    add_to_cart,
    add_admin_user,
    cart_total,
    change_cart_quantity,
    clear_cart,
    create_category,
    create_order_from_cart,
    create_product,
    delete_category,
    delete_product,
    ensure_user,
    get_admin_ids,
    get_admin_new_order_template,
    get_admin_products,
    get_all_user_ids_for_broadcast,
    get_cart,
    get_notify_chat_id,
    get_order,
    get_payment_info,
    get_order_items,
    get_product,
    get_shop_stats,
    get_shop_stats_full,
    get_user_profile,
    get_user_bonus,
    get_user_status_template,
    get_user_orders,
    get_delivery_settings,
    get_shop_setting,
    set_shop_setting,
    export_catalog,
    import_catalog,
    init_shop_tables,
    is_admin_user,
    is_payment_enabled,
    is_support_admin,
    list_all_orders,
    list_admin_users,
    list_brands,
    list_categories,
    list_customer_users,
    list_products_paginated,
    render_template,
    remove_admin_user,
    save_order_receipt,
    save_product_rating,
    get_product_rating,
    set_support_admin,
    set_order_receipt_review_status,
    set_user_bonus,
    is_maintenance,
    set_welcome_message,
    is_owner_user,
    update_order_status,
    update_product,
    update_user_contacts,
    toggle_maintenance,
    wishlist_has,
    wishlist_list,
    wishlist_toggle,
)
from .shop_state import (
    AdminAddProduct,
    AdminBroadcast,
    AdminCategory,
    AdminCatalogImport,
    AdminEditProduct,
    AdminUsers,
    AdminWelcome,
    CheckoutForm,
    OrderReceiptForm,
    ProfileForm,
    SearchForm,
)

router = Router(name="shop")
init_shop_tables()

PER_PAGE = 6

DELIVERY_NOVA = "Новая почта"
DELIVERY_CITY = "По городу"

DELIVERY_LABELS = {
    "nova": "Новая почта",
    "city": "По городу",
    "pickup": "Самовывоз",
}

PAYMENT_MAP = {
    "cod": "Наложенный платеж",
    "card": "Банковская карта",
    "applepay": "Apple Pay",
    "googlepay": "Google Pay",
}

PRICE_FILTERS = ["all", "low", "mid", "high"]
PREPAID_METHODS = {"card", "applepay", "googlepay"}


def _is_admin(user_id: int) -> bool:
    return is_admin_user(user_id)


def _is_owner(user_id: int) -> bool:
    return is_owner_user(user_id)


def _role_label(role: str) -> str:
    return {
        "owner": "Главный админ",
        "admin": "Админ",
        "user": "Клиент",
    }.get(role, role)


def _available_payment_methods() -> list[tuple[str, str]]:
    methods: list[tuple[str, str]] = []
    if is_payment_enabled("cod"):
        methods.append(("cod", PAYMENT_MAP["cod"]))
    for code in ("card", "applepay", "googlepay"):
        if get_payment_info(code):
            methods.append((code, PAYMENT_MAP[code]))
    return methods


def _payment_instruction_text(method: str) -> str:
    if method not in PREPAID_METHODS:
        return ""
    info = get_payment_info(method)
    if not info:
        return ""
    if method == "card" and "<code>" not in info.lower():
        match = re.search(r"(\d[\d\s-]{10,}\d)", info)
        if match:
            number = match.group(1)
            info = info.replace(number, f"<code>{number}</code>", 1)
        else:
            info = f"<code>{info}</code>"
    return f"\n\n<b>Реквизиты для оплаты</b>\n{info}"


def _is_prepay_payment(payment_label: str) -> bool:
    return payment_label in {PAYMENT_MAP[code] for code in PREPAID_METHODS}


def _order_back_target(status_raw: str) -> str:
    if status_raw in _ARCHIVE_STATUSES:
        return "menu:orders:archive"
    if status_raw in _INWORK_STATUSES:
        return "menu:orders:inwork"
    return "menu:orders:new"


def _parse_profile_address(address: str) -> tuple[str, str]:
    # Ожидаемый формат: "г. <город>, отделение: <номер/название>"
    raw = (address or "").strip()
    if not raw:
        return "", ""
    city = raw
    branch = ""
    if "," in raw:
        left, right = raw.split(",", 1)
        city = left.replace("г.", "").strip()
        branch = right.replace("отделение:", "").strip()
    return city, branch


def _split_full_name(name: str) -> tuple[str, str, str]:
    parts = [p for p in (name or "").strip().split() if p]
    if not parts:
        return "", "", ""
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""
    middle_name = " ".join(parts[2:]) if len(parts) > 2 else ""
    return first_name, last_name, middle_name


def _orders_for_viewer(user_id: int) -> list[dict]:
    if _is_admin(user_id):
        return list_all_orders(limit=500)
    return get_user_orders(user_id)


def _receipt_status_text(order: dict) -> str:
    if not order.get("receipt_sent", False):
        return "не отправлен"
    status = str(order.get("receipt_review_status", "")).strip().lower()
    if status == "approved":
        return "подтвержден"
    if status == "rejected":
        return "отклонен"
    return "на проверке"


def _filter_orders_by_receipt(orders: list[dict], flt: str) -> tuple[list[dict], str]:
    if flt == "pending":
        return [o for o in orders if o.get("receipt_sent") and str(o.get("receipt_review_status", "")).strip().lower() in {"", "pending"}], "⏳ Заказы: чек на проверке"
    if flt == "approved":
        return [o for o in orders if str(o.get("receipt_review_status", "")).strip().lower() == "approved"], "✅ Заказы: чек подтвержден"
    if flt == "rejected":
        return [o for o in orders if str(o.get("receipt_review_status", "")).strip().lower() == "rejected"], "❌ Заказы: чек отклонен"
    if flt == "has":
        return [o for o in orders if o.get("receipt_sent")], "📎 Заказы: с чеком"
    return [o for o in orders if not o.get("receipt_sent")], "🚫 Заказы: без чека"


async def _render_admin_categories(message: Message, viewer_id: int) -> None:
    categories = list_categories()
    if not categories:
        await _safe_edit(message, "Категорий пока нет", reply_markup=admin_categories_kb([]))
        return
    await _safe_edit(message, "<b>🗂 Категории</b>", reply_markup=admin_categories_kb(categories))


def _user_display_name(message_or_callback: Message | CallbackQuery) -> str:
    user = message_or_callback.from_user
    return user.first_name or user.username or str(user.id)


async def _check_maintenance(callback: CallbackQuery) -> bool:
    if is_maintenance() and not _is_admin(callback.from_user.id):
        await callback.answer("🛠 Техработы: каталог и корзина временно недоступны. Статус заказов доступен.", show_alert=True)
        return True
    return False


def _price_range(code: str) -> tuple[int | None, int | None]:
    if code == "low":
        return 0, 10000
    if code == "mid":
        return 10001, 30000
    if code == "high":
        return 30001, None
    return None, None


def _next_in_list(values: list[str], current: str) -> str:
    if current not in values:
        return values[0]
    idx = values.index(current)
    return values[(idx + 1) % len(values)]


async def _safe_edit(message: Message, text: str, reply_markup=None) -> None:
    if reply_markup is None:
        reply_markup = back_menu_kb()
    try:
        if message.photo:
            await message.edit_caption(caption=text, reply_markup=reply_markup)
        else:
            await message.edit_text(text, reply_markup=reply_markup)
        return
    except TelegramBadRequest as error:
        err = str(error).lower()
        if "message is not modified" in err:
            return
        if "there is no text in the message to edit" in err or "there is no caption in the message to edit" in err:
            await message.answer(text, reply_markup=reply_markup)
            return
        raise


async def _render_admin_user_card(message: Message, viewer_id: int, target_user_id: int) -> None:
    profile = get_user_profile(target_user_id)
    orders = get_user_orders(target_user_id)
    order_count = len(orders)
    total_spent = sum(o["total"] for o in orders)
    bonus = profile.get("bonus", 0)
    back_target = "admin:admins:list" if profile["role"] in {"owner", "admin"} else "admin:users:list"
    bonus_line = f"🎁 Бонус: <b>{bonus} грн</b>\n" if bonus > 0 else ""
    text = (
        "<b>👤 Карточка пользователя</b>\n"
        f"🆔 ID: <code>{profile['telegram_id']}</code>\n"
        f"🛡 Роль: <b>{_role_label(profile['role'])}</b>\n"
        f"🙍 ФИО: <b>{profile['name'] or '-'}</b>\n"
        f"📞 Телефон: <b>{profile['phone'] or '-'}</b>\n"
        f"📍 Адрес: <b>{profile['address'] or '-'}</b>\n"
        f"🛟 Техподдержка: <b>{'Да' if is_support_admin(profile['telegram_id']) else 'Нет'}</b>\n"
        f"🛒 Покупок: <b>{order_count}</b>  |  Итого: <b>{total_spent} грн</b>\n"
        f"{bonus_line}"
        f"📅 Дата: <b>{profile['created_at'] or '-'}</b>"
    )
    await _safe_edit(
        message,
        text,
        reply_markup=admin_user_actions_kb(
            target_user_id,
            is_admin=profile["role"] in {"owner", "admin"},
            is_owner=profile["role"] == "owner",
            can_manage_admins=_is_owner(viewer_id),
            is_support=is_support_admin(profile["telegram_id"]),
            back_target=back_target,
        ),
    )


def _get_catalog_state(data: dict) -> dict:
    filters = data.get("catalog_filters") or {}
    return {
        "category_id": filters.get("category_id"),
        "search": filters.get("search"),
        "stock_only": bool(filters.get("stock_only", False)),
        "price": filters.get("price", "all"),
        "brand": filters.get("brand", "all"),
        "brand_options": filters.get("brand_options", []),
        "page": int(filters.get("page", 1)),
    }


async def _set_catalog_state(state: FSMContext, new_state: dict) -> None:
    await state.update_data(catalog_filters=new_state)


def _apply_brand_options(category_id: int | None) -> list[str]:
    brands = list_brands(category_id=category_id)
    return ["all", *brands]


async def _render_catalog(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    st = _get_catalog_state(data)
    st["brand_options"] = _apply_brand_options(st["category_id"])
    if st["brand"] not in st["brand_options"]:
        st["brand"] = "all"

    min_price, max_price = _price_range(st["price"])
    brand = None if st["brand"] == "all" else st["brand"]

    products, total = list_products_paginated(
        category_id=st["category_id"],
        search=st["search"],
        only_available=st["stock_only"],
        min_price=min_price,
        max_price=max_price,
        brand=brand,
        page=st["page"],
        per_page=PER_PAGE,
    )

    total_pages = max(1, ceil(total / PER_PAGE))
    if st["page"] > total_pages:
        st["page"] = total_pages
        await _set_catalog_state(state, st)
        products, total = list_products_paginated(
            category_id=st["category_id"],
            search=st["search"],
            only_available=st["stock_only"],
            min_price=min_price,
            max_price=max_price,
            brand=brand,
            page=st["page"],
            per_page=PER_PAGE,
        )

    if not products:
        await _safe_edit(
            callback.message,
            "<b>Товары не найдены. Измените фильтры.</b>",
            reply_markup=categories_kb(list_categories()),
        )
        return

    price_label = {
        "all": "любая",
        "low": "до 10 000",
        "mid": "10 001 - 30 000",
        "high": "от 30 001",
    }.get(st["price"], "любая")
    stock_label = "только в наличии" if st["stock_only"] else "любой"

    text = (
        "<b>🗂 Каталог</b>\n"
        f"<i>Фильтры:</i> Цена: {price_label} | Наличие: {stock_label}"
    )
    await _safe_edit(
        callback.message,
        text,
        reply_markup=catalog_kb(products, page=st["page"], total_pages=max(1, ceil(total / PER_PAGE))),
    )


@router.callback_query(F.data == "menu:catalog")
async def catalog_root(callback: CallbackQuery, state: FSMContext) -> None:
    if await _check_maintenance(callback):
        return
    ensure_user(callback.from_user.id, _user_display_name(callback))
    await _set_catalog_state(
        state,
        {
            "category_id": None,
            "search": None,
            "stock_only": False,
            "price": "all",
            "brand": "all",
            "brand_options": ["all"],
            "page": 1,
        },
    )
    await _safe_edit(callback.message, "<b>📂 Категории</b>", reply_markup=categories_kb(list_categories()))
    await callback.answer()


@router.callback_query(F.data.startswith("shop:cat:"))
async def catalog_by_category(callback: CallbackQuery, state: FSMContext) -> None:
    if await _check_maintenance(callback):
        return
    category_id = int(callback.data.split(":")[-1])
    await _set_catalog_state(
        state,
        {
            "category_id": category_id,
            "search": None,
            "stock_only": False,
            "price": "all",
            "brand": "all",
            "brand_options": _apply_brand_options(category_id),
            "page": 1,
        },
    )
    await _render_catalog(callback, state)
    await callback.answer()


@router.callback_query(F.data == "shop:search")
async def search_start(callback: CallbackQuery, state: FSMContext) -> None:
    if await _check_maintenance(callback):
        return
    await state.set_state(SearchForm.query)
    await _safe_edit(callback.message, "Введите запрос для поиска товара:", reply_markup=back_menu_kb("menu:catalog"))
    await callback.answer()


@router.message(SearchForm.query)
async def search_run(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    await state.clear()
    if not query:
        await message.answer("Пустой запрос")
        return

    await _set_catalog_state(
        state,
        {
            "category_id": None,
            "search": query,
            "stock_only": False,
            "price": "all",
            "brand": "all",
            "brand_options": _apply_brand_options(None),
            "page": 1,
        },
    )
    fake = type("Obj", (), {"message": message, "from_user": message.from_user})
    await _render_catalog(fake, state)  # type: ignore[arg-type]


@router.callback_query(F.data == "shop:page:prev")
async def catalog_prev_page(callback: CallbackQuery, state: FSMContext) -> None:
    st = _get_catalog_state(await state.get_data())
    st["page"] = max(1, st["page"] - 1)
    await _set_catalog_state(state, st)
    await _render_catalog(callback, state)
    await callback.answer()


@router.callback_query(F.data == "shop:page:next")
async def catalog_next_page(callback: CallbackQuery, state: FSMContext) -> None:
    st = _get_catalog_state(await state.get_data())
    st["page"] = st["page"] + 1
    await _set_catalog_state(state, st)
    await _render_catalog(callback, state)
    await callback.answer()


@router.callback_query(F.data == "shop:filter:stock")
async def filter_stock(callback: CallbackQuery, state: FSMContext) -> None:
    st = _get_catalog_state(await state.get_data())
    st["stock_only"] = not st["stock_only"]
    st["page"] = 1
    await _set_catalog_state(state, st)
    await _render_catalog(callback, state)
    await callback.answer("Фильтр наличия изменен")


@router.callback_query(F.data == "shop:filter:price")
async def filter_price(callback: CallbackQuery, state: FSMContext) -> None:
    st = _get_catalog_state(await state.get_data())
    st["price"] = _next_in_list(PRICE_FILTERS, st["price"])
    st["page"] = 1
    await _set_catalog_state(state, st)
    await _render_catalog(callback, state)
    await callback.answer("Фильтр цены изменен")


@router.callback_query(F.data == "shop:filter:brand")
async def filter_brand(callback: CallbackQuery, state: FSMContext) -> None:
    st = _get_catalog_state(await state.get_data())
    options = st.get("brand_options") or _apply_brand_options(st["category_id"])
    st["brand"] = _next_in_list(options, st["brand"])
    st["page"] = 1
    await _set_catalog_state(state, st)
    await _render_catalog(callback, state)
    await callback.answer("Фильтр бренда изменен")


@router.callback_query(F.data == "shop:filter:reset")
async def filter_reset(callback: CallbackQuery, state: FSMContext) -> None:
    st = _get_catalog_state(await state.get_data())
    st["stock_only"] = False
    st["price"] = "all"
    st["brand"] = "all"
    st["search"] = None
    st["page"] = 1
    await _set_catalog_state(state, st)
    await _render_catalog(callback, state)
    await callback.answer("Фильтры сброшены")


@router.callback_query(F.data.startswith("shop:product:"))
async def product_open(callback: CallbackQuery) -> None:
    if await _check_maintenance(callback):
        return
    product_id = int(callback.data.split(":")[-1])
    product = get_product(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    stock_text = "✅ В наличии" if product["stock"] > 0 else "❌ Нет в наличии"
    rating = get_product_rating(product_id)
    if rating["count"] > 0:
        stars_filled = "⭐" * round(rating["avg"])
        rating_line = f"⭐ Рейтинг: <b>{rating['avg']}/5</b> {stars_filled} ({rating['count']} оценок)\n"
    else:
        rating_line = ""
    caption = (
        f"<b>{product['name']}</b>\n\n"
        f"💰 Цена: <b>{product['price']} грн</b>\n"
        f"📦 В наличии: <b>{stock_text}</b>\n"
        f"🏷 Категория: <b>{product['category_name']}</b>\n"
        f"{rating_line}\n"
        f"Описание:\n{product['description']}"
    )
    in_wishlist = wishlist_has(callback.from_user.id, product_id)

    if product["photo"]:
        await callback.message.delete()
        await callback.message.answer_photo(
            product["photo"],
            caption=caption,
            reply_markup=product_kb(product_id, in_wishlist=in_wishlist),
        )
    else:
        await _safe_edit(callback.message, caption, reply_markup=product_kb(product_id, in_wishlist=in_wishlist))

    await callback.answer()


@router.callback_query(F.data.startswith("shop:wishlist:toggle:"))
async def wishlist_toggle_handler(callback: CallbackQuery) -> None:
    if await _check_maintenance(callback):
        return
    product_id = int(callback.data.split(":")[-1])
    added = wishlist_toggle(callback.from_user.id, product_id)
    await callback.answer("Добавлено в избранное" if added else "Удалено из избранного")


@router.callback_query(F.data == "menu:wishlist")
async def wishlist_show(callback: CallbackQuery, state: FSMContext) -> None:
    if await _check_maintenance(callback):
        return
    await state.update_data(wishlist_page=1)
    items = wishlist_list(callback.from_user.id)
    if not items:
        await _safe_edit(
            callback.message,
            "<b>Избранное пустое</b>",
            reply_markup=main_menu_inline_kb(is_admin=_is_admin(callback.from_user.id)),
        )
        await callback.answer()
        return

    page = 1
    total_pages = max(1, ceil(len(items) / PER_PAGE))
    chunk = items[:PER_PAGE]
    await _safe_edit(callback.message, "<b>❤️ Избранное</b>", reply_markup=wishlist_kb(chunk, page=page, total_pages=total_pages))
    await callback.answer()


@router.callback_query(F.data.startswith("shop:wishlist:page:"))
async def wishlist_page(callback: CallbackQuery, state: FSMContext) -> None:
    if await _check_maintenance(callback):
        return
    data = await state.get_data()
    page = int(data.get("wishlist_page", 1))
    mode = callback.data.split(":")[-1]
    items = wishlist_list(callback.from_user.id)
    total_pages = max(1, ceil(len(items) / PER_PAGE))

    if mode == "prev":
        page = max(1, page - 1)
    else:
        page = min(total_pages, page + 1)

    await state.update_data(wishlist_page=page)
    start = (page - 1) * PER_PAGE
    chunk = items[start : start + PER_PAGE]
    await _safe_edit(callback.message, "<b>❤️ Избранное</b>", reply_markup=wishlist_kb(chunk, page=page, total_pages=total_pages))
    await callback.answer()


@router.callback_query(F.data.startswith("shop:add:"))
async def cart_add(callback: CallbackQuery) -> None:
    if await _check_maintenance(callback):
        return
    product_id = int(callback.data.split(":")[-1])
    ok, text = add_to_cart(callback.from_user.id, product_id, 1)
    if ok:
        in_wishlist = wishlist_has(callback.from_user.id, product_id)
        try:
            await callback.message.edit_reply_markup(
                reply_markup=product_kb(product_id, in_wishlist=in_wishlist, show_cart_button=True)
            )
        except TelegramBadRequest:
            pass
    await callback.answer(text, show_alert=not ok)


@router.callback_query(F.data == "menu:cart")
async def cart_show(callback: CallbackQuery) -> None:
    if await _check_maintenance(callback):
        return
    items = get_cart(callback.from_user.id)
    if not items:
        await _safe_edit(
            callback.message,
            "<b>🛒 Корзина пустая</b>",
            reply_markup=main_menu_inline_kb(is_admin=_is_admin(callback.from_user.id)),
        )
        await callback.answer()
        return

    lines = [f"• {item['title']} — {item['quantity']} шт x {item['price']} грн" for item in items]
    text = "<b>🛒 Ваша корзина</b>\n\n" + "\n".join(lines)
    text += f"\n\nИтого: <b>{cart_total(callback.from_user.id)} грн</b>"
    await _safe_edit(callback.message, text, reply_markup=cart_kb(items))
    await callback.answer()


@router.callback_query(F.data.startswith("shop:cart:inc:"))
async def cart_inc(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":")[-1])
    ok, text = change_cart_quantity(callback.from_user.id, product_id, 1)
    await callback.answer(text, show_alert=not ok)
    await cart_show(callback)


@router.callback_query(F.data.startswith("shop:cart:dec:"))
async def cart_dec(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":")[-1])
    ok, text = change_cart_quantity(callback.from_user.id, product_id, -1)
    await callback.answer(text, show_alert=not ok)
    await cart_show(callback)


@router.callback_query(F.data.startswith("shop:cart:remove:"))
async def cart_remove(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":")[-1])
    change_cart_quantity(callback.from_user.id, product_id, -9999)
    await callback.answer("Удалено")
    await cart_show(callback)


@router.callback_query(F.data == "shop:cart:clear")
async def cart_clear(callback: CallbackQuery) -> None:
    clear_cart(callback.from_user.id)
    await _safe_edit(callback.message, "<b>Корзина очищена</b>", reply_markup=back_menu_kb("menu:cart"))
    await callback.answer()


@router.callback_query(F.data == "shop:checkout:start")
async def checkout_start(callback: CallbackQuery, state: FSMContext) -> None:
    if await _check_maintenance(callback):
        return
    if not get_cart(callback.from_user.id):
        await callback.answer("Корзина пустая", show_alert=True)
        return

    await state.set_state(CheckoutForm.delivery_method)
    ds = get_delivery_settings()
    await _safe_edit(
        callback.message,
        "Выберите способ доставки:",
        reply_markup=checkout_delivery_kb(nova=ds["nova"], city=ds["city"], pickup=ds["pickup"]),
    )
    await callback.answer()


@router.callback_query(CheckoutForm.delivery_method, F.data.startswith("shop:delivery:"))
async def checkout_delivery_select(callback: CallbackQuery, state: FSMContext) -> None:
    delivery_key = callback.data.split(":")[-1]
    delivery_label = DELIVERY_LABELS.get(delivery_key, "Новая почта")
    await state.update_data(checkout_delivery=delivery_label, checkout_delivery_key=delivery_key)

    if delivery_key == "city":
        # Особый флоу для доставки По городу
        await state.set_state(CheckoutForm.city_recip_name)
        await _safe_edit(callback.message, "🏙 Доставка по городу\n\nВведите имя получателя:", reply_markup=back_menu_kb("menu:cart"))
        await callback.answer()
        return

    # Для остальных доставок — стандартный флоу
    profile = get_user_profile(callback.from_user.id)
    profile_name = (profile.get("name") or "").strip()
    profile_phone = (profile.get("phone") or "").strip()
    profile_address = (profile.get("address") or "").strip()
    if profile_name and profile_phone and profile_address:
        await state.update_data(
            profile_name=profile_name,
            profile_phone=profile_phone,
            profile_address=profile_address,
        )
        await state.set_state(CheckoutForm.payment)
        await _safe_edit(
            callback.message,
            f"Доставка: <b>{delivery_label}</b>\nДанные получателя взяты из личного кабинета.\nВыберите оплату:",
            reply_markup=checkout_payment_kb(_available_payment_methods()),
        )
        await callback.answer()
        return

    await state.set_state(CheckoutForm.first_name)
    await _safe_edit(callback.message, "Введите имя получателя:", reply_markup=back_menu_kb("menu:cart"))
    await callback.answer()


# ─── City delivery FSM ───────────────────────────────────────────────────────

@router.message(CheckoutForm.city_recip_name)
async def checkout_city_recip_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Введите корректное имя получателя:")
        return
    await state.update_data(checkout_full_name=name)
    await state.set_state(CheckoutForm.city_recip_address)
    await message.answer(
        "Введите адрес доставки (улица, дом и подъезд):",
        reply_markup=back_menu_kb("menu:cart"),
    )


@router.message(CheckoutForm.city_recip_address)
async def checkout_city_recip_address(message: Message, state: FSMContext) -> None:
    address = (message.text or "").strip()
    if len(address) < 5:
        await message.answer(
            "Введите корректный адрес доставки (улица, дом и подъезд):",
            reply_markup=back_menu_kb("menu:cart"),
        )
        return
    await state.update_data(checkout_delivery_address=address)
    await state.set_state(CheckoutForm.city_recip_phone)
    await message.answer("Введите номер телефона получателя:")


@router.message(CheckoutForm.city_recip_phone)
async def checkout_city_recip_phone(message: Message, state: FSMContext) -> None:
    phone = (message.text or "").strip()
    if len(phone) < 7:
        await message.answer("Некорректный телефон. Введите снова:")
        return
    await state.update_data(checkout_phone=phone)
    await state.set_state(CheckoutForm.payment)
    await message.answer(
        "Выберите оплату:",
        reply_markup=checkout_city_payment_kb(),
    )


@router.message(CheckoutForm.first_name)
async def checkout_first_name(message: Message, state: FSMContext) -> None:
    first_name = (message.text or "").strip()
    if len(first_name) < 2:
        await message.answer("Введите корректное имя")
        return
    await state.update_data(first_name=first_name)
    await state.set_state(CheckoutForm.last_name)
    await message.answer("Введите фамилию получателя:")


@router.message(CheckoutForm.last_name)
async def checkout_last_name(message: Message, state: FSMContext) -> None:
    last_name = (message.text or "").strip()
    if len(last_name) < 2:
        await message.answer("Введите корректную фамилию")
        return
    await state.update_data(last_name=last_name)
    await state.set_state(CheckoutForm.middle_name)
    await message.answer("Введите отчество получателя:")


@router.message(CheckoutForm.middle_name)
async def checkout_middle_name(message: Message, state: FSMContext) -> None:
    middle_name = (message.text or "").strip()
    if len(middle_name) < 2:
        await message.answer("Введите корректное отчество")
        return
    await state.update_data(middle_name=middle_name)
    await state.set_state(CheckoutForm.phone)
    await message.answer("Введите номер телефона:")


@router.message(CheckoutForm.phone)
async def checkout_phone(message: Message, state: FSMContext) -> None:
    phone = (message.text or "").strip()
    if len(phone) < 7:
        await message.answer("Некорректный телефон. Введите снова:")
        return

    await state.update_data(phone=phone)
    await state.set_state(CheckoutForm.city)
    await message.answer("Введите город:")


@router.message(CheckoutForm.city)
async def checkout_city(message: Message, state: FSMContext) -> None:
    city = (message.text or "").strip()
    if len(city) < 2:
        await message.answer("Введите корректный город")
        return
    await state.update_data(city=city)
    await state.set_state(CheckoutForm.branch)
    await message.answer("Введите отделение Новой почты:")


@router.message(CheckoutForm.branch)
async def checkout_branch(message: Message, state: FSMContext) -> None:
    branch = (message.text or "").strip()
    if len(branch) < 1:
        await message.answer("Введите отделение Новой почты")
        return

    await state.update_data(branch=branch)
    await state.set_state(CheckoutForm.payment)
    await message.answer(
        "Выберите оплату:",
        reply_markup=checkout_payment_kb(_available_payment_methods()),
    )


@router.callback_query(CheckoutForm.payment, F.data.startswith("shop:pay:"))
async def checkout_payment(callback: CallbackQuery, state: FSMContext) -> None:
    key = callback.data.split(":")[-1]
    payment = PAYMENT_MAP.get(key)
    if not payment:
        await callback.answer("Неизвестный тип оплаты", show_alert=True)
        return

    data = await state.get_data()
    delivery_key = str(data.get("checkout_delivery_key") or "")

    # Для доставки "По городу" разрешаем только оплату картой.
    if delivery_key == "city" and key != "card":
        await callback.answer("Для доставки по городу доступна только оплата картой", show_alert=True)
        return

    if delivery_key == "city":
        full_name = (data.get("checkout_full_name") or "").strip()
        phone = (data.get("checkout_phone") or "").strip()
        delivery_address = (data.get("checkout_delivery_address") or "").strip()
    else:
        profile_name = (data.get("profile_name") or "").strip()
        profile_phone = (data.get("profile_phone") or "").strip()
        profile_address = (data.get("profile_address") or "").strip()

        full_name = profile_name or " ".join(
            part for part in [
                (data.get("first_name") or "").strip(),
                (data.get("last_name") or "").strip(),
                (data.get("middle_name") or "").strip(),
            ]
            if part
        )
        delivery_address = profile_address or f"г. {data.get('city', '')}, отделение: {data.get('branch', '')}".strip().strip(",")
        phone = profile_phone or (data.get("phone") or "").strip()

    if not full_name or not phone or not delivery_address:
        await state.clear()
        await callback.answer("Не хватает данных получателя. Заполните данные и повторите.", show_alert=True)
        return

    # Сохраняем всё нужное для создания заказа и проверяем бонус
    bonus = get_user_bonus(callback.from_user.id)
    await state.update_data(
        checkout_payment_key=key,
        checkout_payment=payment,
        checkout_full_name=full_name,
        checkout_phone=phone,
        checkout_delivery_address=delivery_address,
    )

    if bonus > 0:
        await state.set_state(CheckoutForm.bonus_confirm)
        cart_sum = cart_total(callback.from_user.id)
        await _safe_edit(
            callback.message,
            f"🎁 У вас есть бонус: <b>{bonus} грн</b>\n"
            f"Сумма заказа: <b>{cart_sum} грн</b>\n"
            f"С бонусом: <b>{max(1, cart_sum - bonus)} грн</b>\n\n"
            "Использовать бонус?",
            reply_markup=checkout_bonus_kb(bonus),
        )
        await callback.answer()
        return

    await _finalize_checkout(callback, state, use_bonus=False)


async def _finalize_checkout(callback: CallbackQuery, state: FSMContext, *, use_bonus: bool) -> None:
    data = await state.get_data()
    key = data.get("checkout_payment_key", "")
    payment = data.get("checkout_payment", "")
    full_name = data.get("checkout_full_name", "")
    phone = data.get("checkout_phone", "")
    delivery_address = data.get("checkout_delivery_address", "")
    delivery = data.get("checkout_delivery", DELIVERY_NOVA)
    user_id = callback.from_user.id

    bonus = get_user_bonus(user_id) if use_bonus else 0

    ok, payload = create_order_from_cart(
        user_id,
        name=full_name,
        phone=phone,
        address=delivery_address,
        delivery=delivery,
        payment=payment,
        discount=bonus,
    )
    await state.clear()

    if not ok:
        await callback.answer(payload, show_alert=True)
        return

    if use_bonus and bonus > 0:
        set_user_bonus(user_id, 0)

    order = get_order(payload)
    if order:
        admin_message = render_template(
            get_admin_new_order_template(),
            {
                "order_id": order["order_id"],
                "name": order["name"],
                "phone": order["phone"],
                "total": order["total"],
                "delivery": order["delivery"],
                "payment": order["payment"],
                "status": order["status"],
            },
        )
        for admin_id in get_admin_ids():
            try:
                await callback.bot.send_message(
                    int(admin_id),
                    admin_message,
                    reply_markup=admin_order_status_kb(
                        order["order_id"],
                        order["user_id"],
                        has_receipt=False,
                        payment_label=order.get("payment", ""),
                    ),
                )
            except Exception:
                pass

        notify_chat_id = get_notify_chat_id()
        if notify_chat_id:
            try:
                await callback.bot.send_message(
                    int(notify_chat_id),
                    admin_message,
                    reply_markup=admin_order_status_kb(
                        order["order_id"],
                        order["user_id"],
                        has_receipt=False,
                        payment_label=order.get("payment", ""),
                    ),
                )
            except Exception:
                pass

    payment_info = _payment_instruction_text(key)
    can_send_receipt = key in PREPAID_METHODS
    bonus_line = f"\n🎁 Бонус применён: <b>-{bonus} грн</b>" if use_bonus and bonus > 0 else ""
    total_line = f"\nСумма к оплате: <b>{order['total']} грн</b>" if order else ""
    await _safe_edit(
        callback.message,
        f"✅ Заказ оформлен\nНомер: <code>{payload}</code>{total_line}{bonus_line}{payment_info}",
        reply_markup=order_detail_kb(payload, back_target="menu:orders", can_send_receipt=can_send_receipt),
    )
    await callback.answer("Готово")


@router.callback_query(CheckoutForm.bonus_confirm, F.data == "shop:bonus:use")
async def checkout_bonus_use(callback: CallbackQuery, state: FSMContext) -> None:
    await _finalize_checkout(callback, state, use_bonus=True)


@router.callback_query(CheckoutForm.bonus_confirm, F.data == "shop:bonus:skip")
async def checkout_bonus_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await _finalize_checkout(callback, state, use_bonus=False)


@router.callback_query(F.data.startswith("shop:rate:"))
async def product_rate(callback: CallbackQuery) -> None:
    # format: shop:rate:{order_id}:{product_id}:{stars}
    parts = callback.data.split(":")
    if len(parts) < 5:
        await callback.answer("Ошибка", show_alert=True)
        return
    order_id = parts[2]
    product_id = int(parts[3])
    stars = int(parts[4])
    saved = save_product_rating(order_id, callback.from_user.id, product_id, stars)
    if saved:
        try:
            await callback.message.delete()
        except Exception:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        await callback.answer(f"Оценка {stars}/5 сохранена!")
    else:
        try:
            await callback.message.delete()
        except Exception:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        await callback.answer("Вы уже оценили этот товар", show_alert=True)



_NEW_STATUSES = {"Новый"}
_INWORK_STATUSES = {"Оплачен", "Отправлен"}
_ARCHIVE_STATUSES = {"Доставлен", "Отменен"}


@router.callback_query(F.data == "menu:orders")
async def orders_show(callback: CallbackQuery) -> None:
    orders = _orders_for_viewer(callback.from_user.id)
    has_new = any(o.get("status_raw", "") in _NEW_STATUSES for o in orders)
    has_inwork = any(o.get("status_raw", "") in _INWORK_STATUSES for o in orders)
    has_archive = any(o.get("status_raw", "") in _ARCHIVE_STATUSES for o in orders)
    if not orders:
        await _safe_edit(callback.message, "<b>У вас пока нет заказов</b>", reply_markup=back_menu_kb("menu:profile"))
        await callback.answer()
        return
    await _safe_edit(
        callback.message,
        "<b>📦 Мои заказы</b>\nВыберите раздел:",
        reply_markup=orders_menu_kb(
            has_new=has_new,
            has_inwork=has_inwork,
            has_archive=has_archive,
            has_receipt_search=True,
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:orders:receipt:search")
async def orders_receipt_search(callback: CallbackQuery) -> None:
    orders = _orders_for_viewer(callback.from_user.id)
    if not orders:
        await callback.answer("Заказов пока нет", show_alert=True)
        return
    await _safe_edit(
        callback.message,
        "<b>Поиск заказов по чеку</b>\nВыберите фильтр:",
        reply_markup=orders_receipt_filter_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("menu:orders:receipt:filter:"))
async def orders_receipt_filter(callback: CallbackQuery) -> None:
    orders = _orders_for_viewer(callback.from_user.id)
    flt = callback.data.split(":")[-1]
    filtered, title = _filter_orders_by_receipt(orders, flt)

    if not filtered:
        await _safe_edit(
            callback.message,
            f"<b>{title}</b>\nНичего не найдено",
            reply_markup=orders_receipt_filter_kb(),
        )
        await callback.answer()
        return

    await _safe_edit(callback.message, f"<b>{title}</b>", reply_markup=orders_list_kb(filtered))
    await callback.answer()


@router.callback_query(F.data == "menu:orders:new")
async def orders_new_show(callback: CallbackQuery) -> None:
    orders = _orders_for_viewer(callback.from_user.id)
    new = [o for o in orders if o.get("status_raw", "") in _NEW_STATUSES]
    if not new:
        await callback.answer("Новых заказов нет", show_alert=True)
        return
    await _safe_edit(
        callback.message,
        "<b>🔵 Новые заказы</b>",
        reply_markup=orders_new_kb(new),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:orders:inwork")
async def orders_inwork_show(callback: CallbackQuery) -> None:
    orders = _orders_for_viewer(callback.from_user.id)
    inwork = [o for o in orders if o.get("status_raw", "") in _INWORK_STATUSES]
    if not inwork:
        await callback.answer("Заказов в работе нет", show_alert=True)
        return
    await _safe_edit(
        callback.message,
        "<b>🔄 В работе</b>",
        reply_markup=orders_inwork_kb(inwork),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:orders:archive")
async def orders_archive_show(callback: CallbackQuery) -> None:
    orders = _orders_for_viewer(callback.from_user.id)
    archived = [o for o in orders if o.get("status_raw", "") in _ARCHIVE_STATUSES]
    if not archived:
        await callback.answer("Архив пуст", show_alert=True)
        return
    await _safe_edit(
        callback.message,
        "<b>📁 Архив заказов</b>",
        reply_markup=orders_archive_kb(archived),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("shop:order:"))
async def order_open(callback: CallbackQuery) -> None:
    order_id = callback.data.split(":", 2)[-1]
    order = get_order(order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    viewer_is_admin = _is_admin(callback.from_user.id)
    if not viewer_is_admin and int(order["user_id"]) != int(callback.from_user.id):
        await callback.answer("Нет доступа к этому заказу", show_alert=True)
        return

    items = get_order_items(order_id)
    lines = [f"• {item['title']} — {item['quantity']} x {item['price']} грн" for item in items]
    if viewer_is_admin:
        text = (
            f"<b>📦 Заказ {order_id}</b>\n"
            f"📌 Статус: <b>{order['status']}</b>\n"
            f"👤 Клиент: <b>{order['name']}</b>\n"
            f"📞 Телефон: <b>{order['phone']}</b>\n"
            f"📍 Адрес: <b>{order['address']}</b>\n"
            f"🚚 Доставка: <b>{order['delivery']}</b>\n"
            f"💳 Оплата: <b>{order['payment']}</b>\n"
            f"🧾 Чек: <b>{_receipt_status_text(order)}</b>\n"
            f"💰 Итого: <b>{order['total']} грн</b>\n\n"
            f"{chr(10).join(lines)}"
        )
        receipt_pending = bool(order.get("receipt_sent", False)) and str(order.get("receipt_review_status", "")).strip().lower() in {"", "pending"}
        kb = admin_order_status_kb(
            order_id,
            order["user_id"],
            receipt_pending=receipt_pending,
            has_receipt=bool(order.get("receipt_sent", False)),
            current_status_raw=order.get("status_raw", ""),
            payment_label=order.get("payment", ""),
        )
    else:
        text = (
            f"<b>📦 Заказ {order_id}</b>\n"
            f"📌 Статус: <b>{order['status']}</b>\n"
            f"🚚 Доставка: <b>{order['delivery']}</b>\n"
            f"💳 Оплата: <b>{order['payment']}</b>\n"
            f"🧾 Чек: <b>{_receipt_status_text(order)}</b>\n"
            f"💰 Итого: <b>{order['total']} грн</b>\n\n"
            f"{chr(10).join(lines)}"
        )
        raw = order.get("status_raw", "")
        receipt_review = str(order.get("receipt_review_status", "")).strip().lower()
        can_send_receipt = _is_prepay_payment(order.get("payment", "")) and (
            not order.get("receipt_sent", False) or receipt_review == "rejected"
        )
        kb = order_detail_kb(order_id, back_target=_order_back_target(raw), can_send_receipt=can_send_receipt)
    await _safe_edit(callback.message, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("shop:receipt:start:"))
async def order_receipt_start(callback: CallbackQuery, state: FSMContext) -> None:
    order_id = callback.data.split(":", 3)[-1]
    order = get_order(order_id)
    if not order or int(order["user_id"]) != int(callback.from_user.id):
        await callback.answer("Заказ не найден", show_alert=True)
        return
    if not _is_prepay_payment(order.get("payment", "")):
        await callback.answer("Для этого способа оплаты чек не нужен", show_alert=True)
        return
    receipt_review = str(order.get("receipt_review_status", "")).strip().lower()
    if order.get("receipt_sent", False) and receipt_review != "rejected":
        await callback.answer("Чек уже был отправлен, ожидайте подтверждения", show_alert=True)
        return

    await state.set_state(OrderReceiptForm.file)
    await state.update_data(receipt_order_id=order_id)
    await _safe_edit(
        callback.message,
        "Отправьте чек: фото или PDF файлом",
        reply_markup=back_menu_kb(f"shop:order:{order_id}"),
    )
    await callback.answer()


@router.message(OrderReceiptForm.file, F.photo)
async def order_receipt_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    order_id = str(data.get("receipt_order_id", "")).strip()
    if not order_id:
        await state.clear()
        await message.answer("Не удалось определить заказ", reply_markup=back_menu_kb("menu:orders"))
        return

    file_id = message.photo[-1].file_id
    ok = save_order_receipt(order_id, file_id=file_id, file_type="photo")
    if not ok:
        await state.clear()
        await message.answer("Чек уже был отправлен, ожидайте подтверждения", reply_markup=back_menu_kb(f"shop:order:{order_id}"))
        return

    order = get_order(order_id)
    caption = (
        f"🧾 Получен чек от клиента\n"
        f"Заказ: {order_id}\n"
        f"Клиент: {message.from_user.id}\n"
        f"Оплата: <b>{order['payment'] if order else '-'}</b>"
    )
    admin_kb = admin_order_status_kb(
        order_id,
        order["user_id"] if order else None,
        receipt_pending=True,
        has_receipt=True,
        payment_label=order.get("payment", "") if order else "",
    )
    for admin_id in get_admin_ids():
        try:
            await message.bot.send_photo(int(admin_id), file_id, caption=caption, reply_markup=admin_kb)
        except Exception:
            pass
    notify_chat_id = get_notify_chat_id()
    if notify_chat_id:
        try:
            await message.bot.send_photo(int(notify_chat_id), file_id, caption=caption, reply_markup=admin_kb)
        except Exception:
            pass

    await state.clear()
    await message.answer("✅ Чек отправлен. Ожидайте подтверждения", reply_markup=back_menu_kb(f"shop:order:{order_id}"))


@router.message(OrderReceiptForm.file, F.document)
async def order_receipt_pdf(message: Message, state: FSMContext) -> None:
    doc = message.document
    is_pdf = bool(doc and ((doc.mime_type or "").lower() == "application/pdf" or (doc.file_name or "").lower().endswith(".pdf")))
    if not is_pdf:
        await message.answer("Нужен PDF документ или фото", reply_markup=back_menu_kb("menu:orders"))
        return

    data = await state.get_data()
    order_id = str(data.get("receipt_order_id", "")).strip()
    if not order_id:
        await state.clear()
        await message.answer("Не удалось определить заказ", reply_markup=back_menu_kb("menu:orders"))
        return

    ok = save_order_receipt(order_id, file_id=doc.file_id, file_type="pdf")
    if not ok:
        await state.clear()
        await message.answer("Чек уже был отправлен, ожидайте подтверждения", reply_markup=back_menu_kb(f"shop:order:{order_id}"))
        return

    order = get_order(order_id)
    caption = (
        f"🧾 Получен чек от клиента\n"
        f"Заказ: {order_id}\n"
        f"Клиент: {message.from_user.id}\n"
        f"Оплата: <b>{order['payment'] if order else '-'}</b>"
    )
    admin_kb = admin_order_status_kb(
        order_id,
        order["user_id"] if order else None,
        receipt_pending=True,
        has_receipt=True,
        payment_label=order.get("payment", "") if order else "",
    )
    for admin_id in get_admin_ids():
        try:
            await message.bot.send_document(int(admin_id), doc.file_id, caption=caption, reply_markup=admin_kb)
        except Exception:
            pass
    notify_chat_id = get_notify_chat_id()
    if notify_chat_id:
        try:
            await message.bot.send_document(int(notify_chat_id), doc.file_id, caption=caption, reply_markup=admin_kb)
        except Exception:
            pass

    await state.clear()
    await message.answer("✅ Чек отправлен. Ожидайте подтверждения", reply_markup=back_menu_kb(f"shop:order:{order_id}"))


@router.message(OrderReceiptForm.file)
async def order_receipt_invalid(message: Message) -> None:
    await message.answer("Отправьте фото чека или PDF файл", reply_markup=back_menu_kb("menu:orders"))


@router.callback_query(F.data == "profile:edit")
async def profile_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileForm.first_name)
    await _safe_edit(callback.message, "Введите имя:", reply_markup=back_menu_kb("menu:profile"))
    await callback.answer()


@router.message(ProfileForm.first_name)
async def profile_first_name_save(message: Message, state: FSMContext) -> None:
    first_name = (message.text or "").strip()
    if len(first_name) < 2:
        await message.answer("Введите корректное имя")
        return
    await state.update_data(first_name=first_name)
    await state.set_state(ProfileForm.last_name)
    await message.answer("Введите фамилию:")


@router.message(ProfileForm.last_name)
async def profile_last_name_save(message: Message, state: FSMContext) -> None:
    last_name = (message.text or "").strip()
    if len(last_name) < 2:
        await message.answer("Введите корректную фамилию")
        return
    await state.update_data(last_name=last_name)
    await state.set_state(ProfileForm.middle_name)
    await message.answer("Введите отчество:")


@router.message(ProfileForm.middle_name)
async def profile_middle_name_save(message: Message, state: FSMContext) -> None:
    middle_name = (message.text or "").strip()
    if len(middle_name) < 2:
        await message.answer("Введите корректное отчество")
        return
    await state.update_data(middle_name=middle_name)
    await state.set_state(ProfileForm.phone)
    await message.answer("Введите телефон:")


@router.message(ProfileForm.phone)
async def profile_phone_save(message: Message, state: FSMContext) -> None:
    phone = (message.text or "").strip()
    if len(phone) < 7:
        await message.answer("Некорректный телефон. Введите снова:")
        return
    await state.update_data(phone=phone)
    await state.set_state(ProfileForm.city)
    await message.answer("Введите город:")


@router.message(ProfileForm.city)
async def profile_city_save(message: Message, state: FSMContext) -> None:
    city = (message.text or "").strip()
    if len(city) < 2:
        await message.answer("Введите корректный город")
        return
    await state.update_data(city=city)
    await state.set_state(ProfileForm.branch)
    await message.answer("Введите отделение Новой почты:")


@router.message(ProfileForm.branch)
async def profile_branch_save(message: Message, state: FSMContext) -> None:
    branch = (message.text or "").strip()
    if len(branch) < 1:
        await message.answer("Введите отделение Новой почты")
        return

    data = await state.get_data()
    full_name = " ".join(
        part
        for part in [
            (data.get("first_name") or "").strip(),
            (data.get("last_name") or "").strip(),
            (data.get("middle_name") or "").strip(),
        ]
        if part
    )
    address = f"г. {data.get('city', '').strip()}, отделение: {branch}"
    update_user_contacts(
        message.from_user.id,
        name=full_name,
        phone=(data.get("phone") or "").strip(),
        address=address,
    )
    await state.clear()
    await message.answer("Данные обновлены", reply_markup=profile_actions_inline_kb)


@router.callback_query(F.data == "admin:maintenance:toggle")
async def admin_toggle_maintenance(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    enabled = toggle_maintenance()
    try:
        await callback.message.edit_reply_markup(reply_markup=admin_menu_inline_kb(maintenance_enabled=enabled))
    except TelegramBadRequest:
        pass
    await callback.answer("Тех.работы ВКЛ" if enabled else "Тех.работы ВЫКЛ", show_alert=True)


@router.callback_query(F.data == "admin:welcome:edit")
async def admin_welcome_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(AdminWelcome.text)
    await _safe_edit(callback.message, "Введите новый текст стартового сообщения:", reply_markup=back_admin_kb())
    await callback.answer()


@router.message(AdminWelcome.text)
async def admin_welcome_text(message: Message, state: FSMContext) -> None:
    await state.update_data(welcome_text=(message.text or "").strip())
    await state.set_state(AdminWelcome.photo)
    await message.answer("Отправьте фото для стартового сообщения или '-' без фото")


@router.message(AdminWelcome.photo, F.photo)
async def admin_welcome_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    set_welcome_message(data.get("welcome_text", "Добро пожаловать"), message.photo[-1].file_id)
    await state.clear()
    await message.answer("✅ Стартовое сообщение обновлено (с фото)")


@router.message(AdminWelcome.photo)
async def admin_welcome_no_photo(message: Message, state: FSMContext) -> None:
    if (message.text or "").strip() != "-":
        await message.answer("Отправьте фото или '-' чтобы сохранить без фото")
        return

    data = await state.get_data()
    set_welcome_message(data.get("welcome_text", "Добро пожаловать"), "")
    await state.clear()
    await message.answer("✅ Стартовое сообщение обновлено (без фото)")


@router.callback_query(F.data == "admin:shop")
async def admin_shop(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await _safe_edit(callback.message, "<b>⚙️ Админ панель магазина</b>", reply_markup=admin_shop_kb(_is_owner(callback.from_user.id)))
    await callback.answer()


@router.callback_query(F.data == "admin:delivery:settings")
async def admin_delivery_settings(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    ds = get_delivery_settings()
    await _safe_edit(
        callback.message,
        "<b>🚚 Способы доставки</b>\n\nНажмите на пункт чтобы включить или отключить:",
        reply_markup=admin_delivery_settings_kb(nova=ds["nova"], city=ds["city"], pickup=ds["pickup"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:delivery:toggle:"))
async def admin_delivery_toggle(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    key = callback.data.split(":")[-1]  # nova / city / pickup
    setting_key = f"delivery_{key}_enabled"
    current = get_shop_setting(setting_key, "1")
    new_value = "0" if current == "1" else "1"
    set_shop_setting(setting_key, new_value)

    ds = get_delivery_settings()
    await _safe_edit(
        callback.message,
        "<b>🚚 Способы доставки</b>\n\nНажмите на пункт чтобы включить или отключить:",
        reply_markup=admin_delivery_settings_kb(nova=ds["nova"], city=ds["city"], pickup=ds["pickup"]),
    )
    await callback.answer("✅ Обновлено")


# ─── Экспорт / Импорт каталога ───────────────────────────────────────────────

@router.callback_query(F.data == "admin:catalog:export")
async def admin_catalog_export(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await callback.answer("⏳ Подготавливаю файл...")
    data = export_catalog()
    raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    file = BufferedInputFile(raw, filename="catalog_export.json")
    await callback.message.answer_document(
        file,
        caption=(
            "📤 <b>Экспорт каталога</b>\n"
            f"Категорий: {len(data['categories'])}\n"
            f"Товаров: {sum(len(c['products']) for c in data['categories'])}\n\n"
            "Для импорта нажмите <b>📥 Импорт каталога</b> и отправьте этот файл."
        ),
        reply_markup=back_admin_kb("admin:shop"),
    )


@router.callback_query(F.data == "admin:catalog:import")
async def admin_catalog_import_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(AdminCatalogImport.file)
    await callback.message.answer(
        "📥 <b>Импорт каталога</b>\n\nОтправьте файл <code>catalog_export.json</code> который был экспортирован ранее.",
        reply_markup=back_admin_kb("admin:shop"),
    )
    await callback.answer()


@router.message(AdminCatalogImport.file, F.document)
async def admin_catalog_import_file(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return

    doc = message.document
    if not doc.file_name or not doc.file_name.endswith(".json"):
        await message.answer("❌ Нужен файл .json (catalog_export.json)")
        return

    try:
        file_info = await message.bot.get_file(doc.file_id)
        downloaded = await message.bot.download_file(file_info.file_path)
        raw = downloaded.read()
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        await message.answer(f"❌ Ошибка чтения файла: {e}")
        await state.clear()
        return

    if data.get("version") != 1 or "categories" not in data:
        await message.answer("❌ Неверный формат файла. Ожидается catalog_export.json версии 1.")
        await state.clear()
        return

    try:
        cats, prods = import_catalog(data)
    except Exception as e:
        await message.answer(f"❌ Ошибка импорта: {e}")
        await state.clear()
        return

    await state.clear()
    await message.answer(
        f"✅ <b>Импорт завершён</b>\n\nКатегорий обработано: <b>{cats}</b>\nТоваров добавлено: <b>{prods}</b>",
        reply_markup=back_admin_kb("admin:shop"),
    )


@router.message(AdminCatalogImport.file)
async def admin_catalog_import_wrong(message: Message) -> None:
    await message.answer("❌ Нужен файл .json. Отправьте документ.")


@router.callback_query(F.data == "admin:product:add")
async def admin_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    cats = list_categories()
    if not cats:
        await callback.answer("Сначала создайте хотя бы одну категорию", show_alert=True)
        return

    await state.set_state(AdminAddProduct.category)
    await _safe_edit(
        callback.message,
        "<b>Выберите категорию товара:</b>",
        reply_markup=admin_product_category_kb(cats),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:categories")
async def admin_categories(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await _render_admin_categories(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "admin:category:add")
async def admin_category_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(AdminCategory.name)
    await _safe_edit(callback.message, "Введите название новой категории:", reply_markup=back_admin_kb("admin:categories"))
    await callback.answer()


@router.message(AdminCategory.name)
async def admin_category_add_finish(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    ok, text, _category_id = create_category((message.text or "").strip())
    if not ok:
        await message.answer(text)
        return

    await state.clear()
    await message.answer(text, reply_markup=back_admin_kb("admin:categories"))


@router.callback_query(F.data.startswith("admin:category:view:"))
async def admin_category_view(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    category_id = int(callback.data.split(":")[-1])
    category = next((item for item in list_categories() if item["id"] == category_id), None)
    if not category:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    await _safe_edit(
        callback.message,
        f"<b>Категория</b>\nID: <code>{category['id']}</code>\nНазвание: <b>{category['name']}</b>",
        reply_markup=admin_category_actions_kb(category_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:category:delete:"))
async def admin_category_delete(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    category_id = int(callback.data.split(":")[-1])
    ok, text = delete_category(category_id)
    if not ok:
        await callback.answer(text, show_alert=True)
        return

    await _render_admin_categories(callback.message, callback.from_user.id)
    await callback.answer(text)


@router.callback_query(F.data.startswith("admin:product:catsel:"), AdminAddProduct.category)
async def admin_add_category(callback: CallbackQuery, state: FSMContext) -> None:
    cat_id = int(callback.data.split(":")[-1])
    cats = list_categories()
    cat = next((c for c in cats if c["id"] == cat_id), None)
    if not cat:
        await callback.answer("Категория не найдена", show_alert=True)
        return
    await state.update_data(category=cat["name"])
    await state.set_state(AdminAddProduct.name)
    await _safe_edit(callback.message, "Название товара:")
    await callback.answer()


@router.message(AdminAddProduct.name)
async def admin_add_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=(message.text or "").strip())
    await state.set_state(AdminAddProduct.price)
    await message.answer("Цена (число):")


@router.message(AdminAddProduct.price)
async def admin_add_price(message: Message, state: FSMContext) -> None:
    if not (message.text or "").isdigit():
        await message.answer("Цена должна быть числом")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(AdminAddProduct.description)
    await message.answer("Описание товара:")


@router.message(AdminAddProduct.description)
async def admin_add_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=(message.text or "").strip())
    await state.set_state(AdminAddProduct.stock)
    await message.answer("Количество на складе:")


@router.message(AdminAddProduct.stock)
async def admin_add_stock(message: Message, state: FSMContext) -> None:
    if not (message.text or "").isdigit():
        await message.answer("Количество должно быть числом")
        return
    await state.update_data(stock=int(message.text))
    await state.set_state(AdminAddProduct.photo)
    await message.answer("Отправьте фото товара или '-' для пропуска")


@router.message(AdminAddProduct.photo, F.photo)
async def admin_add_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    from utils.db_api.shop import get_or_create_category

    category_id = get_or_create_category(data.get("category", "Электроника"))
    product_id = create_product(
        name=data.get("name", ""),
        description=data.get("description", ""),
        price=int(data.get("price", 0)),
        stock=int(data.get("stock", 0)),
        category_id=category_id,
        photo=message.photo[-1].file_id,
        brand=data.get("brand", ""),
    )
    await state.clear()
    await message.answer(f"✅ Товар добавлен. ID: {product_id}", reply_markup=back_admin_kb())


@router.message(AdminAddProduct.photo)
async def admin_add_no_photo(message: Message, state: FSMContext) -> None:
    if (message.text or "").strip() != "-":
        await message.answer("Отправьте фото или '-' для пропуска")
        return

    data = await state.get_data()
    from utils.db_api.shop import get_or_create_category

    category_id = get_or_create_category(data.get("category", "Электроника"))
    product_id = create_product(
        name=data.get("name", ""),
        description=data.get("description", ""),
        price=int(data.get("price", 0)),
        stock=int(data.get("stock", 0)),
        category_id=category_id,
        photo="",
        brand=data.get("brand", ""),
    )
    await state.clear()
    await message.answer(f"✅ Товар добавлен. ID: {product_id}", reply_markup=back_admin_kb())


@router.callback_query(F.data == "admin:product:list")
async def admin_products(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    products = get_admin_products()
    if not products:
        await _safe_edit(callback.message, "Товаров нет", reply_markup=admin_shop_kb(_is_owner(callback.from_user.id)))
        await callback.answer()
        return

    await _safe_edit(callback.message, "<b>Товары</b>", reply_markup=admin_products_kb(products))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:product:view:"))
async def admin_product_view(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":")[-1])
    product = get_product(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    text = (
        f"<b>{product['name']}</b>\n"
        f"ID: <code>{product['id']}</code>\n"
        f"Цена: <b>{product['price']} грн</b>\n"
        f"Остаток: <b>{product['stock']} шт</b>\n"
        f"Категория: <b>{product['category_name']}</b>\n"
        f"{product['description']}"
    )
    await _safe_edit(callback.message, text, reply_markup=admin_product_actions_kb(product_id))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:product:price:"))
async def admin_edit_price_start(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[-1])
    await state.set_state(AdminEditProduct.price)
    await state.update_data(edit_product_id=product_id)
    await _safe_edit(callback.message, "Введите новую цену:", reply_markup=back_admin_kb())
    await callback.answer()


@router.message(AdminEditProduct.price)
async def admin_edit_price(message: Message, state: FSMContext) -> None:
    if not (message.text or "").isdigit():
        await message.answer("Цена должна быть числом")
        return
    data = await state.get_data()
    update_product(int(data["edit_product_id"]), price=int(message.text))
    await state.clear()
    await message.answer("Цена обновлена")


@router.callback_query(F.data.startswith("admin:product:stock:"))
async def admin_edit_stock_start(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[-1])
    await state.set_state(AdminEditProduct.stock)
    await state.update_data(edit_product_id=product_id)
    await _safe_edit(callback.message, "Введите новый остаток:", reply_markup=back_admin_kb())
    await callback.answer()


@router.message(AdminEditProduct.stock)
async def admin_edit_stock(message: Message, state: FSMContext) -> None:
    if not (message.text or "").isdigit():
        await message.answer("Остаток должен быть числом")
        return
    data = await state.get_data()
    update_product(int(data["edit_product_id"]), stock=int(message.text))
    await state.clear()
    await message.answer("Остаток обновлен")


@router.callback_query(F.data.startswith("admin:product:photo:"))
async def admin_edit_photo_start(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[-1])
    await state.set_state(AdminEditProduct.photo)
    await state.update_data(edit_product_id=product_id)
    await _safe_edit(callback.message, "Отправьте новое фото товара", reply_markup=back_admin_kb())
    await callback.answer()


@router.message(AdminEditProduct.photo, F.photo)
async def admin_edit_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    update_product(int(data["edit_product_id"]), photo=message.photo[-1].file_id)
    await state.clear()
    await message.answer("Фото обновлено")


@router.callback_query(F.data.startswith("admin:product:delete:"))
async def admin_delete_product(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":")[-1])
    delete_product(product_id)
    await _safe_edit(callback.message, "Товар удален", reply_markup=admin_shop_kb(_is_owner(callback.from_user.id)))
    await callback.answer()


@router.callback_query(F.data == "admin:orders")
async def admin_orders(callback: CallbackQuery) -> None:
    orders = list_all_orders(limit=100)
    if not orders:
        await _safe_edit(callback.message, "Заказов пока нет", reply_markup=admin_shop_kb(_is_owner(callback.from_user.id)))
        await callback.answer()
        return

    has_new = any(o.get("status_raw", "") in _NEW_STATUSES for o in orders)
    has_inwork = any(o.get("status_raw", "") in _INWORK_STATUSES for o in orders)
    has_archive = any(o.get("status_raw", "") in _ARCHIVE_STATUSES for o in orders)
    await _safe_edit(
        callback.message,
        "<b>Список заказов</b>\nВыберите раздел:",
        reply_markup=admin_orders_menu_kb(has_new=has_new, has_inwork=has_inwork, has_archive=has_archive),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:orders:new")
async def admin_orders_new(callback: CallbackQuery) -> None:
    orders = list_all_orders(limit=500)
    filtered = [o for o in orders if o.get("status_raw", "") in _NEW_STATUSES]
    if not filtered:
        await callback.answer("Новых заказов нет", show_alert=True)
        return
    await _safe_edit(callback.message, "<b>🔵 Новые заказы</b>", reply_markup=admin_orders_kb(filtered))
    await callback.answer()


@router.callback_query(F.data == "admin:orders:inwork")
async def admin_orders_inwork(callback: CallbackQuery) -> None:
    orders = list_all_orders(limit=500)
    filtered = [o for o in orders if o.get("status_raw", "") in _INWORK_STATUSES]
    if not filtered:
        await callback.answer("Заказов в работе нет", show_alert=True)
        return
    await _safe_edit(callback.message, "<b>🔄 Заказы в работе</b>", reply_markup=admin_orders_kb(filtered))
    await callback.answer()


@router.callback_query(F.data == "admin:orders:archive")
async def admin_orders_archive(callback: CallbackQuery) -> None:
    orders = list_all_orders(limit=500)
    filtered = [o for o in orders if o.get("status_raw", "") in _ARCHIVE_STATUSES]
    if not filtered:
        await callback.answer("Архив пуст", show_alert=True)
        return
    await _safe_edit(callback.message, "<b>📁 Архив заказов</b>", reply_markup=admin_orders_kb(filtered))
    await callback.answer()


@router.callback_query(F.data == "admin:orders:receipt:search")
async def admin_orders_receipt_search(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await _safe_edit(
        callback.message,
        "<b>Поиск заказов по чеку</b>\nВыберите фильтр:",
        reply_markup=admin_orders_receipt_filter_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:orders:receipt:filter:"))
async def admin_orders_receipt_filter(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    flt = callback.data.split(":")[-1]
    orders = list_all_orders(limit=500)
    filtered, title = _filter_orders_by_receipt(orders, flt)

    if not filtered:
        await _safe_edit(
            callback.message,
            f"<b>{title}</b>\nНичего не найдено",
            reply_markup=admin_orders_receipt_filter_kb(),
        )
        await callback.answer()
        return

    await _safe_edit(callback.message, f"<b>{title}</b>", reply_markup=admin_orders_kb(filtered))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:order:view:"))
async def admin_order_view(callback: CallbackQuery) -> None:
    order_id = callback.data.split(":", 3)[-1]
    order = get_order(order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    items = get_order_items(order_id)
    lines = [f"• {i['title']} — {i['quantity']} x {i['price']} грн" for i in items]
    text = (
        f"<b>📦 Заказ {order_id}</b>\n"
        f"📌 Статус: <b>{order['status']}</b>\n"
        f"👤 Клиент: <b>{order['name']}</b>\n"
        f"📞 Телефон: <b>{order['phone']}</b>\n"
        f"📍 Адрес: <b>{order['address']}</b>\n"
        f"🚚 Доставка: <b>{order['delivery']}</b>\n"
        f"💳 Оплата: <b>{order['payment']}</b>\n"
        f"🧾 Чек: <b>{_receipt_status_text(order)}</b>\n"
        f"💰 Итого: <b>{order['total']} грн</b>\n\n"
        f"{chr(10).join(lines)}"
    )
    receipt_pending = bool(order.get("receipt_sent", False)) and str(order.get("receipt_review_status", "")).strip().lower() in {"", "pending"}
    await _safe_edit(
        callback.message,
        text,
        reply_markup=admin_order_status_kb(
            order_id,
            order["user_id"],
            receipt_pending=receipt_pending,
            has_receipt=bool(order.get("receipt_sent", False)),
            current_status_raw=order.get("status_raw", ""),
            payment_label=order.get("payment", ""),
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:order:status:"))
async def admin_order_status(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    order_id = parts[3]
    status = parts[4]
    update_order_status(order_id, status)

    order = get_order(order_id)
    items = get_order_items(order_id)
    lines = [f"• {i['title']} — {i['quantity']} x {i['price']} грн" for i in items]
    text = (
        f"<b>📦 Заказ {order_id}</b>\n"
        f"📌 Статус: <b>{order['status']}</b>\n"
        f"👤 Клиент: <b>{order['name']}</b>\n"
        f"📞 Телефон: <b>{order['phone']}</b>\n"
        f"📍 Адрес: <b>{order['address']}</b>\n"
        f"🚚 Доставка: <b>{order['delivery']}</b>\n"
        f"💳 Оплата: <b>{order['payment']}</b>\n"
        f"🧾 Чек: <b>{_receipt_status_text(order)}</b>\n"
        f"💰 Итого: <b>{order['total']} грн</b>\n\n"
        f"{chr(10).join(lines)}"
    )
    receipt_pending = bool(order.get("receipt_sent", False)) and str(order.get("receipt_review_status", "")).strip().lower() in {"", "pending"}
    await _safe_edit(
        callback.message,
        text,
        reply_markup=admin_order_status_kb(
            order_id,
            order["user_id"],
            receipt_pending=receipt_pending,
            has_receipt=bool(order.get("receipt_sent", False)),
            current_status_raw=order.get("status_raw", ""),
            payment_label=order.get("payment", ""),
        ),
    )

    try:
        await callback.bot.send_message(
            order["user_id"],
            render_template(
                get_user_status_template(),
                {
                    "order_id": order["order_id"],
                    "status": order["status"],
                    "name": order["name"],
                    "phone": order["phone"],
                    "total": order["total"],
                    "delivery": order["delivery"],
                    "payment": order["payment"],
                },
            ),
            reply_markup=back_menu_kb("menu:orders"),
        )
    except Exception:
        pass

    # Опрос качества при доставке
    if status == "done":
        for item in items:
            pid = item.get("product_id")
            if not pid:
                continue
            product = get_product(pid)
            caption = f"⭐ Оцените качество продукта\n<b>{item['title']}</b>"
            try:
                if product and product.get("photo"):
                    await callback.bot.send_photo(
                        order["user_id"],
                        photo=product["photo"],
                        caption=caption,
                        reply_markup=product_survey_kb(order_id, pid),
                    )
                else:
                    await callback.bot.send_message(
                        order["user_id"],
                        caption,
                        reply_markup=product_survey_kb(order_id, pid),
                    )
            except Exception:
                pass

    await callback.answer(f"📌 Статус обновлен: {order['status']}")


@router.callback_query(F.data.startswith("admin:order:receipt:"))
async def admin_order_receipt_review(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    order_id = parts[3]
    action = parts[4]
    if action == "view":
        order = get_order(order_id)
        if not order or not order.get("receipt_sent", False):
            await callback.answer("Чек не найден", show_alert=True)
            return

        caption = (
            f"🧾 Чек по заказу {order_id}\n"
            f"Клиент: {order['user_id']}\n"
            f"Статус чека: {_receipt_status_text(order)}"
        )
        try:
            if order.get("receipt_file_type") == "pdf":
                await callback.message.answer_document(
                    order["receipt_file_id"],
                    caption=caption,
                    reply_markup=back_admin_kb("admin:orders"),
                )
            else:
                await callback.message.answer_photo(
                    order["receipt_file_id"],
                    caption=caption,
                    reply_markup=back_admin_kb("admin:orders"),
                )
        except Exception:
            await callback.answer("Не удалось открыть чек", show_alert=True)
            return

        await callback.answer()
        return

    if action not in {"approve", "reject"}:
        await callback.answer("Неизвестное действие", show_alert=True)
        return
    new_status = "approved" if action == "approve" else "rejected"

    updated = set_order_receipt_review_status(order_id, new_status)
    if not updated:
        await callback.answer("Чек уже обработан или не найден", show_alert=True)
        return

    if new_status == "approved":
        update_order_status(order_id, "paid")

    order = get_order(order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    items = get_order_items(order_id)
    lines = [f"• {i['title']} — {i['quantity']} x {i['price']} грн" for i in items]
    text = (
        f"<b>📦 Заказ {order_id}</b>\n"
        f"📌 Статус: <b>{order['status']}</b>\n"
        f"👤 Клиент: <b>{order['name']}</b>\n"
        f"📞 Телефон: <b>{order['phone']}</b>\n"
        f"📍 Адрес: <b>{order['address']}</b>\n"
        f"🚚 Доставка: <b>{order['delivery']}</b>\n"
        f"💳 Оплата: <b>{order['payment']}</b>\n"
        f"🧾 Чек: <b>{_receipt_status_text(order)}</b>\n"
        f"💰 Итого: <b>{order['total']} грн</b>\n\n"
        f"{chr(10).join(lines)}"
    )
    await _safe_edit(
        callback.message,
        text,
        reply_markup=admin_order_status_kb(
            order_id,
            order["user_id"],
            receipt_pending=False,
            has_receipt=bool(order.get("receipt_sent", False)),
            current_status_raw=order.get("status_raw", ""),
            payment_label=order.get("payment", ""),
        ),
    )

    user_text = (
        f"✅ Чек по заказу <code>{order_id}</code> подтвержден администратором."
        if new_status == "approved"
        else f"❌ Чек по заказу <code>{order_id}</code> отклонен. Отправьте чек повторно в карточке заказа."
    )
    try:
        await callback.bot.send_message(
            int(order["user_id"]),
            user_text,
            reply_markup=back_menu_kb("menu:main"),
        )
    except Exception:
        pass

    await callback.answer("Чек подтвержден" if new_status == "approved" else "Чек отклонен")


@router.callback_query(F.data == "admin:users:list")
async def admin_users_list(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    users = list_customer_users()
    if not users:
        await _safe_edit(callback.message, "Клиентов пока нет", reply_markup=admin_shop_kb(_is_owner(callback.from_user.id)))
        await callback.answer()
        return

    await _safe_edit(callback.message, "<b>👥 Клиенты</b>", reply_markup=admin_people_kb(users, back_target="admin:shop"))
    await callback.answer()


@router.callback_query(F.data == "admin:admins:list")
async def admin_admins_list(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    admins = list_admin_users()
    await _safe_edit(
        callback.message,
        "<b>🛡 Админы</b>",
        reply_markup=admin_people_kb(admins, back_target="admin:shop", add_admin_button=_is_owner(callback.from_user.id)),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:admins:add")
async def admin_add_admin_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer("Только главный админ может управлять администраторами", show_alert=True)
        return

    await state.set_state(AdminUsers.add_admin_id)
    await _safe_edit(callback.message, "Отправьте Telegram ID пользователя, которому нужно выдать права админа:", reply_markup=back_admin_kb("admin:admins:list"))
    await callback.answer()


@router.message(AdminUsers.add_admin_id)
async def admin_add_admin_finish(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        await state.clear()
        return

    raw_value = (message.text or "").strip()
    if not raw_value.isdigit():
        await message.answer("Нужен числовой Telegram ID")
        return

    target_user_id = int(raw_value)
    add_admin_user(target_user_id)
    await state.clear()
    await message.answer(f"Пользователь <code>{target_user_id}</code> теперь админ.")


@router.callback_query(F.data.startswith("admin:user:view:"))
async def admin_user_view(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    target_user_id = int(callback.data.split(":")[-1])
    await _render_admin_user_card(callback.message, callback.from_user.id, target_user_id)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:user:promote:"))
async def admin_user_promote(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer("Только главный админ может управлять администраторами", show_alert=True)
        return

    target_user_id = int(callback.data.split(":")[-1])
    add_admin_user(target_user_id)
    await _render_admin_user_card(callback.message, callback.from_user.id, target_user_id)
    await callback.answer("Права админа выданы")


@router.callback_query(F.data.startswith("admin:user:demote:"))
async def admin_user_demote(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer("Только главный админ может управлять администраторами", show_alert=True)
        return

    target_user_id = int(callback.data.split(":")[-1])
    if not remove_admin_user(target_user_id):
        await callback.answer("Нельзя снять главного админа", show_alert=True)
        return

    await _render_admin_user_card(callback.message, callback.from_user.id, target_user_id)
    await callback.answer("Админ снят")


@router.callback_query(F.data.startswith("admin:user:support:enable:"))
async def admin_user_support_enable(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer("Только главный админ может назначать техподдержку", show_alert=True)
        return

    target_user_id = int(callback.data.split(":")[-1])
    set_support_admin(target_user_id, True)
    await _render_admin_user_card(callback.message, callback.from_user.id, target_user_id)
    await callback.answer("Назначен в техподдержку")


@router.callback_query(F.data.startswith("admin:user:support:disable:"))
async def admin_user_support_disable(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer("Только главный админ может назначать техподдержку", show_alert=True)
        return

    target_user_id = int(callback.data.split(":")[-1])
    set_support_admin(target_user_id, False)
    await _render_admin_user_card(callback.message, callback.from_user.id, target_user_id)
    await callback.answer("Убран из техподдержки")


@router.callback_query(F.data.startswith("admin:user:orders:"))
async def admin_user_orders(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    target_user_id = int(callback.data.split(":")[-1])
    orders = get_user_orders(target_user_id)

    if not orders:
        text = f"<b>🛒 Покупки пользователя <code>{target_user_id}</code></b>\n\nПокупок нет."
        await _safe_edit(
            callback.message,
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅ Назад", callback_data=f"admin:user:view:{target_user_id}")]
            ]),
        )
        await callback.answer()
        return

    lines = [f"<b>🛒 Покупки пользователя <code>{target_user_id}</code></b>\n"]
    for order in orders:
        oid = order["order_id"]
        items = get_order_items(oid)
        items_text = "\n".join(
            f"    • {it['title']} × {it['quantity']} — {it['price']} грн"
            for it in items
        ) if items else "    (товары не найдены)"
        lines.append(
            f"📦 <b>Заказ #{oid}</b> [{order['status']}]\n"
            f"   💰 Сумма: {order['total']} грн\n"
            f"   🚚 Доставка: {order.get('delivery', '-')}\n"
            f"   💳 Оплата: {order.get('payment', '-')}\n"
            f"   📅 Дата: {order.get('created_at', '-')}\n"
            f"{items_text}"
        )

    text = "\n\n".join(lines)
    # Telegram limit: 4096 chars
    if len(text) > 4096:
        text = text[:4090] + "\n…"

    await _safe_edit(
        callback.message,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ Назад", callback_data=f"admin:user:view:{target_user_id}")]
        ]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:user:bonus:"))
async def admin_user_bonus_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    target_user_id = int(callback.data.split(":")[-1])
    current = get_user_bonus(target_user_id)
    await state.set_state(AdminUsers.bonus_amount)
    await state.update_data(bonus_target_user_id=target_user_id)
    await _safe_edit(
        callback.message,
        f"Текущий бонус пользователя <code>{target_user_id}</code>: <b>{current} грн</b>\n\n"
        "Введите новое значение бонуса (число в гривнах, 0 — сбросить):",
        reply_markup=back_admin_kb(f"admin:user:view:{target_user_id}"),
    )
    await callback.answer()


@router.message(AdminUsers.bonus_amount)
async def admin_user_bonus_set(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Введите целое число (например: 150):")
        return

    amount = int(raw)
    data = await state.get_data()
    target_user_id = int(data.get("bonus_target_user_id", 0))
    if not target_user_id:
        await state.clear()
        return

    set_user_bonus(target_user_id, amount)
    await state.clear()

    # Уведомляем пользователя о начислении/обновлении бонуса
    try:
        await message.bot.send_message(
            target_user_id,
            f"🎁 Вам начислен бонус: <b>{amount} грн</b>",
            reply_markup=back_menu_kb("menu:profile"),
        )
    except Exception:
        pass

    await message.answer(
        f"✅ Бонус пользователя <code>{target_user_id}</code> установлен: <b>{amount} грн</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 К карточке", callback_data=f"admin:user:view:{target_user_id}")]
        ]),
    )


@router.callback_query(F.data.startswith("admin:user:msg:"))
async def admin_user_message_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    target_user_id = int(callback.data.split(":")[-1])
    await state.set_state(AdminUsers.message_text)
    await state.update_data(target_user_id=target_user_id, message_back_target=f"admin:user:view:{target_user_id}")
    await _safe_edit(callback.message, f"Введите сообщение для пользователя <code>{target_user_id}</code>:", reply_markup=back_admin_kb(f"admin:user:view:{target_user_id}"))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:order:msg:"))
async def admin_order_message_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    order_id = callback.data.split(":")[-1]
    order = get_order(order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    await state.set_state(AdminUsers.message_text)
    await state.update_data(target_user_id=order["user_id"], message_back_target=f"admin:order:view:{order_id}")
    await _safe_edit(callback.message, f"Введите сообщение для покупателя заказа <code>{order_id}</code>:", reply_markup=back_admin_kb(f"admin:order:view:{order_id}"))
    await callback.answer()


@router.message(AdminUsers.message_text)
async def admin_user_message_send(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Сообщение не может быть пустым")
        return

    data = await state.get_data()
    target_user_id = int(data.get("target_user_id", 0))
    back_target = str(data.get("message_back_target", "admin:shop"))
    await state.clear()

    if not target_user_id:
        await message.answer("Не найден получатель")
        return

    try:
        await message.bot.send_message(target_user_id, text)
        await message.answer(
            f"Сообщение отправлено пользователю <code>{target_user_id}</code>.",
            reply_markup=back_admin_kb(back_target),
        )
    except Exception:
        await message.answer("Не удалось отправить сообщение. Возможно, пользователь не запускал бота или заблокировал его.")


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBroadcast.text)
    await _safe_edit(callback.message, "Введите текст рассылки:", reply_markup=back_admin_kb())
    await callback.answer()


@router.message(AdminBroadcast.text)
async def admin_broadcast_send(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    user_ids = get_all_user_ids_for_broadcast()
    sent = 0
    for uid in user_ids:
        try:
            await message.bot.send_message(uid, text)
            sent += 1
        except Exception:
            pass
    await state.clear()
    await message.answer(f"Рассылка завершена. Отправлено: {sent}")


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    s = get_shop_stats_full()

    text = (
        "📊 <b>Статистика магазина</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "🛍 <b>Каталог</b>\n"
        f"  📦 Товаров всего: <b>{s['total_products']}</b> в <b>{s['categories']}</b> категориях\n"
        f"  ✅ В наличии: <b>{s['in_stock']}</b> позиций ({s['total_units']} шт)\n"
        f"  ❌ Нет в наличии: <b>{s['out_of_stock']}</b> позиций\n"
        "\n"
        "👥 <b>Клиенты</b>: <b>{customers}</b>\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📅 <b>Сегодня</b>\n"
        f"  🧾 Заказов: <b>{s['orders_day']}</b> | 📦 Продано: <b>{s['sold_day']} шт</b>\n"
        f"  💰 Выручка: <b>{s['revenue_day']} грн</b>\n"
        "\n"
        "📅 <b>Эта неделя</b>\n"
        f"  🧾 Заказов: <b>{s['orders_week']}</b> | 📦 Продано: <b>{s['sold_week']} шт</b>\n"
        f"  💰 Выручка: <b>{s['revenue_week']} грн</b>\n"
        "\n"
        "📅 <b>Этот месяц</b>\n"
        f"  🧾 Заказов: <b>{s['orders_month']}</b> | 📦 Продано: <b>{s['sold_month']} шт</b>\n"
        f"  💰 Выручка: <b>{s['revenue_month']} грн</b>\n"
        "\n"
        "🗂 <b>За всё время</b>\n"
        f"  🧾 Заказов: <b>{s['orders_all']}</b> | 📦 Продано: <b>{s['sold_all']} шт</b>\n"
        f"  💰 Выручка: <b>{s['revenue_all']} грн</b>\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📌 <b>Статусы заказов</b>\n"
        f"  🔵 Новые: <b>{s['orders_new']}</b>\n"
        f"  🔄 В работе: <b>{s['orders_inwork']}</b>\n"
        f"  ✅ Доставлено: <b>{s['orders_done']}</b>\n"
        f"  ❌ Отменено: <b>{s['orders_cancel']}</b>"
    ).format(customers=s["customers"])

    await _safe_edit(
        callback.message,
        text,
        reply_markup=back_admin_kb("admin:shop"),
    )
    await callback.answer()


@router.callback_query(F.data == "shop:noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()
