from math import ceil
import datetime
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
    admin_section_appearance_kb,
    admin_section_catalog_kb,
    admin_section_insights_kb,
    admin_section_io_kb,
    admin_section_payments_kb,
    admin_section_team_kb,
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
from data.config import DEFAULT_SHOP_MENU_CAPTION
from keyboards.inline.user_inline import main_menu_inline_kb, profile_actions_inline_kb, admin_text_menus_kb, admin_text_menu_actions_kb, admin_text_menu_cancel_kb
from utils.db_api.shop import (
    add_to_cart,
    add_admin_user,
    cart_total,
    change_cart_quantity,
    clear_cart,
    clear_user_applied_promo,
    create_category,
    create_order_from_cart,
    create_product,
    create_promocode,
    delete_category,
    delete_product,
    delete_promocode_id,
    ensure_user,
    export_orders_csv,
    get_admin_ids,
    get_admin_new_order_template,
    get_admin_products,
    get_all_user_ids_for_broadcast,
    get_analytics_extended,
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
    get_user_applied_promo,
    get_delivery_settings,
    get_shop_setting,
    set_shop_setting,
    export_catalog,
    import_catalog,
    init_shop_tables,
    is_admin_user,
    is_payment_enabled,
    is_privileged_admin,
    is_support_admin,
    is_user_status_notification_enabled,
    list_all_orders,
    list_admin_users,
    list_categories,
    list_customer_users,
    list_products_paginated,
    list_product_review_snippets,
    list_promocodes,
    list_recent_views,
    promo_discount_for_user_cart,
    render_template,
    remove_admin_user,
    save_order_receipt,
    save_product_rating,
    get_product_rating,
    record_product_view,
    set_support_admin,
    set_order_receipt_review_status,
    set_user_applied_promo,
    set_user_bonus,
    set_user_role,
    toggle_promocode_id,
    update_product_rating_comment,
    is_maintenance,
    is_within_business_hours,
    get_business_hours_bounds,
    set_welcome_message,
    is_owner_user,
    update_order_status,
    update_product,
    update_user_contacts,
    wishlist_has,
    wishlist_list,
    wishlist_toggle,
    wishlist_user_ids_for_product,
    get_text_menus,
    get_text_menu,
    set_text_menu,
    delete_text_menu,
    get_main_menu_message,
    set_main_menu_message,
)
from utils.ui_sections import ui_panel, ui_screen
from .shop_state import (
    AdminAddProduct,
    AdminBroadcast,
    AdminCategory,
    AdminCatalogImport,
    AdminEditProduct,
    AdminMainMenu,
    AdminPromoCreate,
    AdminTextMenu,
    AdminUsers,
    AdminWelcome,
    CartPromoForm,
    CheckoutForm,
    OrderReceiptForm,
    ProfileForm,
    ReviewTextForm,
    SearchForm,
)

router = Router(name="shop")
init_shop_tables()

PER_PAGE = 6
REVIEWS_PER_PAGE = 5

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

PREPAID_METHODS = {"card", "applepay", "googlepay"}

_CHECKOUT_LIKE_FSM = ("CheckoutForm", "OrderReceiptForm", "SearchForm", "CartPromoForm", "ReviewTextForm")


async def _clear_fsm_if_order_flow(state: FSMContext) -> None:
    cur = await state.get_state()
    if not cur:
        return
    if any(m in str(cur) for m in _CHECKOUT_LIKE_FSM):
        await state.clear()


def _is_admin(user_id: int) -> bool:
    return is_admin_user(user_id)


def _is_owner(user_id: int) -> bool:
    return is_owner_user(user_id)


def _is_privileged(user_id: int) -> bool:
    return is_privileged_admin(user_id)


def _admin_shop_markup(viewer_id: int):
    return admin_shop_kb(_is_owner(viewer_id), full_access=_is_privileged(viewer_id))


def _admin_delivery_settings_caption() -> str:
    return ui_panel(
        emoji="🚚",
        title="Способы доставки",
        intro="Нажмите на строку — способ станет доступен или скроется у клиентов.",
        body_lines=["📍 <i>Хотя бы один активный способ упростит оформление заказа.</i>"],
    )


def _admin_shop_screen_text(viewer_id: int) -> str:
    groups = [
        ("🛍", "Каталог и заказы", "Товары, категории, статусы заказов и чеки"),
        ("💳", "Платежи и доставка", "Оплата, реквизиты и способы доставки"),
        ("🛟", "Обращения в поддержку", "Тикеты клиентов в одном месте"),
    ]
    if _is_privileged(viewer_id):
        groups.extend(
            [
                ("📦", "Экспорт и импорт", "Каталог и заказы в файлах"),
                ("👨‍💼", "Команда и промо", "Админы, рассылки и промокоды"),
            ]
        )
    return ui_screen(
        emoji="⚙️",
        title="Управление магазином",
        intro="Подсказки ниже соответствуют кнопкам. Выберите раздел, чтобы продолжить.",
        groups=groups,
    )


def _role_label(role: str) -> str:
    return {
        "owner": "Главный админ",
        "admin": "Админ",
        "manager": "Менеджер",
        "user": "Клиент",
    }.get(role, role)


def _cart_summary(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    items = get_cart(user_id)
    lines = [
        f"• <b>{item['title']}</b>\n  <code>{item['quantity']} × {item['price']} грн</code>"
        for item in items
    ]
    subtotal = cart_total(user_id)
    promo_off, promo_err, promo_code = promo_discount_for_user_cart(user_id)
    applied = bool(get_user_applied_promo(user_id))
    promo_block = ""
    if applied and promo_code and not promo_err and promo_off > 0:
        promo_block = (
            f"\n🏷 Промокод <b>{promo_code}</b>: −<b>{promo_off}</b> грн\n"
            f"💳 После скидки: <b>{subtotal - promo_off}</b> грн"
        )
    elif applied and promo_err:
        promo_block = f"\n⚠️ Промокод: <i>{promo_err}</i>"

    text = (
        "<b>🛒 Корзина</b>\n"
        f"<i>{len(items)} поз.</i>\n"
        "──────────────\n"
        + "\n".join(lines)
        + "\n──────────────\n"
        + f"💰 <b>Итого: {subtotal} грн</b>"
        + promo_block
        + "\n\n<i>Чтобы применить скидку, нажмите «🏷 Промокод» и отправьте код.</i>"
    )
    return text, cart_kb(items, has_promo=applied)


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
        await _safe_edit(message, "📂 Категорий пока нет", reply_markup=admin_categories_kb([]))
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


async def _render_admin_user_card(message: Message, viewer_id: int, target_user_id: int, source: str = "") -> None:
    profile = get_user_profile(target_user_id)
    orders = get_user_orders(target_user_id)
    order_count = len(orders)
    total_spent = sum(o["total"] for o in orders)
    bonus = profile.get("bonus", 0)
    if profile["role"] in {"owner", "admin", "manager"}:
        back_target = "admin:admins:list"
    elif source:
        back_target = f"admin:users:list:{source}"
    else:
        back_target = "admin:users:list"
    bonus_line = f"🎁 Бонус: <b>{bonus} грн</b>\n" if bonus > 0 else ""
    text = (
        "<b>👤 Карточка пользователя</b>\n"
        "──────────────\n"
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
            is_manager=profile["role"] == "manager",
            can_manage_admins=_is_owner(viewer_id),
            is_support=is_support_admin(profile["telegram_id"]),
            back_target=back_target,
            source=source,
        ),
    )


def _get_catalog_state(data: dict) -> dict:
    filters = data.get("catalog_filters") or {}
    return {
        "category_id": filters.get("category_id"),
        "search": filters.get("search"),
        "page": int(filters.get("page", 1)),
    }


async def _set_catalog_state(state: FSMContext, new_state: dict) -> None:
    await state.update_data(catalog_filters=new_state)


async def _render_catalog(source: CallbackQuery | Message, state: FSMContext, *, answer_new: bool = False) -> None:
    data = await state.get_data()
    st = _get_catalog_state(data)

    message = source.message if isinstance(source, CallbackQuery) else source
    use_answer = answer_new and isinstance(source, Message)

    products, total = list_products_paginated(
        category_id=st["category_id"],
        search=st["search"],
        only_available=False,
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
            only_available=False,
            page=st["page"],
            per_page=PER_PAGE,
        )

    if not products:
        empty_text = ui_panel(
            emoji="🔍",
            title="Ничего не нашли",
            intro="Попробуйте другие слова, сократите запрос или откройте категорию.",
            body_lines=["🧭 <i>Кнопки ниже вернут к списку категорий.</i>"],
        )
        if use_answer:
            await message.answer(empty_text, reply_markup=categories_kb(list_categories()))
        else:
            await _safe_edit(message, empty_text, reply_markup=categories_kb(list_categories()))
        return

    if st.get("search"):
        text = ui_panel(
            emoji="🗂",
            title="Каталог",
            intro=f"Результаты по запросу «{st['search']}»",
            body_lines=["🔎 <i>При необходимости измените формулировку или откройте категорию снизу.</i>"],
        )
    else:
        text = ui_panel(
            emoji="🗂",
            title="Каталог",
            intro="Листайте страницы и откройте карточку товара.",
            body_lines=["📋 <i>Назад к категориям — кнопка внизу экрана.</i>"],
        )

    kb = catalog_kb(products, page=st["page"], total_pages=max(1, ceil(total / PER_PAGE)))
    if use_answer:
        await message.answer(text, reply_markup=kb)
    else:
        await _safe_edit(message, text, reply_markup=kb)


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
            "page": 1,
        },
    )
    await _safe_edit(
        callback.message,
        ui_screen(
            emoji="📂",
            title="Категории",
            intro="Выберите раздел витрины или воспользуйтесь поиском.",
            groups=[
                ("📁", "Категории", "Товары сгруппированы по темам"),
                ("🔎", "Поиск", "По названию, описанию и бренду"),
                ("❤️", "Избранное и корзина", "Быстрые кнопки внизу этого экрана"),
            ],
        ),
        reply_markup=categories_kb(list_categories()),
    )
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
    await _safe_edit(
        callback.message,
        ui_panel(
            emoji="🔎",
            title="Поиск по каталогу",
            intro="Отправьте одно сообщение со словом или фразой.",
            body_lines=[
                "📝 <b>Учитываем</b> · название, описание, категория, бренд",
                "✨ <i>Лёгкие опечатки подстрахуем подбором похожих слов</i>",
            ],
        ),
        reply_markup=back_menu_kb("menu:catalog"),
    )
    await callback.answer()


@router.message(SearchForm.query)
async def search_run(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    await state.clear()
    if not query:
        await message.answer(
            "<b>⚠ Пустой запрос</b>\n(<i>введите хотя бы одно слово</i>)",
            reply_markup=back_menu_kb("menu:catalog"),
        )
        return

    await _set_catalog_state(
        state,
        {
            "category_id": None,
            "search": query,
            "page": 1,
        },
    )
    await _render_catalog(message, state, answer_new=True)


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


@router.callback_query(F.data.startswith("shop:product:"))
async def product_open(callback: CallbackQuery) -> None:
    if await _check_maintenance(callback):
        return
    product_id = int(callback.data.split(":")[-1])
    product = get_product(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    record_product_view(callback.from_user.id, product_id)
    stock_text = "✅ В наличии" if product["stock"] > 0 else "❌ Нет в наличии"
    rating = get_product_rating(product_id)
    if rating["count"] > 0:
        stars_filled = "⭐" * round(rating["avg"])
        rating_line = f"⭐ Рейтинг: <b>{rating['avg']}/5</b> {stars_filled} ({rating['count']} оценок)\n"
    else:
        rating_line = ""
    has_reviews = bool(list_product_review_snippets(product_id, limit=1))
    caption = (
        f"<b>📦 {product['name']}</b>\n"
        "──────────────\n"
        f"💰 Цена: <b>{product['price']} грн</b>\n"
        f"📦 В наличии: <b>{stock_text}</b>\n"
        f"🏷 Категория: <b>{product['category_name']}</b>\n"
        f"{rating_line}"
        "\n"
        f"<b>Описание</b>\n{product['description'] or '—'}"
    )
    in_wishlist = wishlist_has(callback.from_user.id, product_id)

    if product["photo"]:
        await callback.message.delete()
        await callback.message.answer_photo(
            product["photo"],
            caption=caption,
            reply_markup=product_kb(product_id, in_wishlist=in_wishlist, has_reviews=has_reviews),
        )
    else:
        await _safe_edit(
            callback.message,
            caption,
            reply_markup=product_kb(product_id, in_wishlist=in_wishlist, has_reviews=has_reviews),
        )

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
            "<b>❤ Избранное пусто</b>\n──────────────\n<i>Сохраняйте товары ⭐ в карточке товара</i>",
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
        has_reviews = bool(list_product_review_snippets(product_id, limit=1))
        try:
            await callback.message.edit_reply_markup(
                reply_markup=product_kb(
                    product_id,
                    in_wishlist=in_wishlist,
                    show_cart_button=True,
                    has_reviews=has_reviews,
                )
            )
        except TelegramBadRequest:
            pass
    await callback.answer(text, show_alert=not ok)


@router.callback_query(F.data.startswith("shop:reviews:"))
async def product_reviews_open(callback: CallbackQuery) -> None:
    if await _check_maintenance(callback):
        return
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("Неверный формат", show_alert=True)
        return

    product_id = int(parts[2])
    page = 1
    if len(parts) >= 4 and str(parts[3]).isdigit():
        page = max(1, int(parts[3]))

    product = get_product(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    snippets = list_product_review_snippets(product_id, limit=100)
    if not snippets:
        await callback.answer("Отзывов пока нет", show_alert=True)
        return

    total_pages = max(1, ceil(len(snippets) / REVIEWS_PER_PAGE))
    page = min(page, total_pages)
    start = (page - 1) * REVIEWS_PER_PAGE
    chunk = snippets[start : start + REVIEWS_PER_PAGE]

    lines_r: list[str] = []
    for s in chunk:
        c = (s.get("comment") or "").strip().replace("\n", " ")
        if len(c) > 300:
            c = c[:297] + "…"
        stars = "⭐" * int(s.get("rating") or 0)
        lines_r.append(f"• «{c}» {stars}")

    text = (
        f"<b>💬 Отзывы: {product['name']}</b>\n"
        "──────────────\n"
        f"<i>Страница {page}/{total_pages}</i>\n\n"
        + "\n".join(lines_r)
    )

    nav_row: list[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(text="⬅", callback_data=f"shop:reviews:{product_id}:{page - 1}")
        )
    nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="shop:noop"))
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton(text="➡", callback_data=f"shop:reviews:{product_id}:{page + 1}")
        )

    rows: list[list[InlineKeyboardButton]] = []
    if nav_row:
        rows.append(nav_row)
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data=f"shop:product:{product_id}")])

    await _safe_edit(
        callback.message,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:cart")
async def cart_show(callback: CallbackQuery, state: FSMContext) -> None:
    if await _check_maintenance(callback):
        return
    await _clear_fsm_if_order_flow(state)
    items = get_cart(callback.from_user.id)
    if not items:
        await _safe_edit(
            callback.message,
            "<b>🛒 Корзина пустая</b>\n──────────────\n<i>Загляните в каталог — там много интересного</i>",
            reply_markup=main_menu_inline_kb(is_admin=_is_admin(callback.from_user.id)),
        )
        await callback.answer()
        return

    text, markup = _cart_summary(callback.from_user.id)
    await _safe_edit(callback.message, text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("shop:cart:inc:"))
async def cart_inc(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[-1])
    ok, text = change_cart_quantity(callback.from_user.id, product_id, 1)
    await callback.answer(text, show_alert=not ok)
    await cart_show(callback, state)


@router.callback_query(F.data.startswith("shop:cart:dec:"))
async def cart_dec(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[-1])
    ok, text = change_cart_quantity(callback.from_user.id, product_id, -1)
    await callback.answer(text, show_alert=not ok)
    await cart_show(callback, state)


@router.callback_query(F.data.startswith("shop:cart:remove:"))
async def cart_remove(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[-1])
    change_cart_quantity(callback.from_user.id, product_id, -9999)
    await callback.answer("Удалено")
    await cart_show(callback, state)


@router.callback_query(F.data == "shop:cart:clear")
async def cart_clear(callback: CallbackQuery) -> None:
    clear_cart(callback.from_user.id)
    clear_user_applied_promo(callback.from_user.id)
    await _safe_edit(
        callback.message,
        "<b>🗑 Корзина очищена</b>\n──────────────\n<i>Можно собрать заказ заново</i>",
        reply_markup=back_menu_kb("menu:cart"),
    )
    await callback.answer()


@router.callback_query(F.data == "shop:cart:promo")
async def cart_promo_start(callback: CallbackQuery, state: FSMContext) -> None:
    if await _check_maintenance(callback):
        return
    if not get_cart(callback.from_user.id):
        await callback.answer("Корзина пустая", show_alert=True)
        return
    await state.set_state(CartPromoForm.code)
    await _safe_edit(
        callback.message,
        "<b>🏷 Промокод</b>\n"
        "──────────────\n"
        "<i>Как применить:</i>\n"
        "1. Введите код одним сообщением\n"
        "2. Отправьте в этот чат\n"
        "3. Скидка применится автоматически\n\n"
        "<i>Пример: <code>SALE10</code></i>",
        reply_markup=back_menu_kb("menu:cart"),
    )
    await callback.answer()


@router.callback_query(F.data == "shop:cart:promo:clear")
async def cart_promo_clear(callback: CallbackQuery, state: FSMContext) -> None:
    clear_user_applied_promo(callback.from_user.id)
    await state.clear()
    await callback.answer("✅ Промокод убран")
    await cart_show(callback, state)


@router.message(CartPromoForm.code)
async def cart_promo_apply(message: Message, state: FSMContext) -> None:
    code = (message.text or "").strip()
    user_id = message.from_user.id
    if not get_cart(user_id):
        await state.clear()
        await message.answer(
            "<b>🛒 Корзина пуста</b>",
            reply_markup=main_menu_inline_kb(is_admin=_is_admin(user_id)),
        )
        return
    set_user_applied_promo(user_id, code)
    off, err, applied = promo_discount_for_user_cart(user_id)
    if err:
        clear_user_applied_promo(user_id)
        await state.clear()
        await message.answer(
            f"<b>❌ {err}</b>\n\n<i>Проверьте написание кода и попробуйте снова.</i>",
            reply_markup=back_menu_kb("menu:cart"),
        )
        return
    await state.clear()
    text, markup = _cart_summary(user_id)
    await message.answer(
        f"<b>✅ Промокод активирован</b>\n"
        f"🏷 Код: <b>{applied}</b>\n"
        f"💸 Скидка: <b>{off} грн</b>\n\n{text}",
        reply_markup=markup,
    )


@router.callback_query(F.data == "menu:recent")
async def recent_views_show(callback: CallbackQuery) -> None:
    if await _check_maintenance(callback):
        return
    rows = list_recent_views(callback.from_user.id, limit=12)
    if not rows:
        await _safe_edit(
            callback.message,
            "<b>👁 Недавние просмотры</b>\n──────────────\n<i>Пока пусто — откройте товары из каталога</i>",
            reply_markup=back_menu_kb("menu:catalog"),
        )
        await callback.answer()
        return

    lines = [f"• <b>{r['name']}</b> — {r['price']} грн" for r in rows]
    kb_rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=f"{r['name'][:28]}", callback_data=f"shop:product:{r['id']}")] for r in rows
    ]
    kb_rows.append([InlineKeyboardButton(text="⬅ Каталог", callback_data="menu:catalog")])
    await _safe_edit(
        callback.message,
        "<b>👁 Недавние просмотры</b>\n──────────────\n" + "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
    )
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
        "<b>🧾 Оформление заказа</b>\n"
        "──────────────\n"
        "Шаг 1/3 • <i>Выберите способ доставки</i>",
        reply_markup=checkout_delivery_kb(nova=ds["nova"], city=ds["city"], pickup=ds["pickup"]),
    )
    await callback.answer()


@router.callback_query(CheckoutForm.delivery_method, F.data.startswith("shop:delivery:"))
async def checkout_delivery_select(callback: CallbackQuery, state: FSMContext) -> None:
    delivery_key = callback.data.split(":")[-1]
    if delivery_key == "city" and not is_within_business_hours():
        hs, he = get_business_hours_bounds()
        await callback.answer(
            f"Доставка по городу с {hs} до {he} (время сервера бота). Сейчас нерабочее время.",
            show_alert=True,
        )
        return

    delivery_label = DELIVERY_LABELS.get(delivery_key, "Новая почта")
    await state.update_data(checkout_delivery=delivery_label, checkout_delivery_key=delivery_key)

    if delivery_key == "city":
        # Особый флоу для доставки По городу
        await state.set_state(CheckoutForm.city_recip_name)
        await _safe_edit(
            callback.message,
            "<b>🚕 Доставка по городу</b>\n──────────────\n👤 <i>Имя получателя:</i>",
            reply_markup=back_menu_kb("menu:cart"),
        )
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
            f"<b>🚚 {delivery_label}</b>\n──────────────\n"
            "✅ Данные получателя взяты из <b>личного кабинета</b>.\n\n"
            "<i>Выберите оплату:</i>",
            reply_markup=checkout_payment_kb(_available_payment_methods()),
        )
        await callback.answer()
        return

    await state.set_state(CheckoutForm.first_name)
    await _safe_edit(
        callback.message,
        "<b>👤 Получатель</b>\n──────────────\n<i>Введите имя:</i>",
        reply_markup=back_menu_kb("menu:cart"),
    )
    await callback.answer()


# ─── City delivery FSM ───────────────────────────────────────────────────────

@router.message(CheckoutForm.city_recip_name)
async def checkout_city_recip_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer(
            "<b>⚠ Слишком коротко</b>\n(<i>минимум 2 символа</i>)",
            reply_markup=back_menu_kb("menu:cart"),
        )
        return
    await state.update_data(checkout_full_name=name)
    await state.set_state(CheckoutForm.city_recip_address)
    await message.answer(
        "<b>📍 Адрес доставки</b>\n──────────────\n"
        "<i>Улица, дом, подъезд — как в навигаторе</i>",
        reply_markup=back_menu_kb("menu:cart"),
    )


@router.message(CheckoutForm.city_recip_address)
async def checkout_city_recip_address(message: Message, state: FSMContext) -> None:
    address = (message.text or "").strip()
    if len(address) < 5:
        await message.answer(
            "<b>⚠ Уточните адрес</b>\n(<i>улица, дом, подъезд — не короче 5 символов</i>)",
            reply_markup=back_menu_kb("menu:cart"),
        )
        return
    await state.update_data(checkout_delivery_address=address)
    await state.set_state(CheckoutForm.city_recip_phone)
    await message.answer(
        "<b>📞 Телефон получателя</b>\n──────────────\n<i>Номер для связи курьера</i>",
        reply_markup=back_menu_kb("menu:cart"),
    )


@router.message(CheckoutForm.city_recip_phone)
async def checkout_city_recip_phone(message: Message, state: FSMContext) -> None:
    phone = (message.text or "").strip()
    if len(phone) < 7:
        await message.answer(
            "<b>⚠ Некорректный телефон</b>\n(<i>попробуйте ещё раз</i>)",
            reply_markup=back_menu_kb("menu:cart"),
        )
        return
    await state.update_data(checkout_phone=phone)
    await state.set_state(CheckoutForm.payment)
    await message.answer(
        "<b>💳 Оплата</b>\n──────────────\n<i>По городу — только карта</i>",
        reply_markup=checkout_city_payment_kb(),
    )


@router.message(CheckoutForm.first_name)
async def checkout_first_name(message: Message, state: FSMContext) -> None:
    first_name = (message.text or "").strip()
    if len(first_name) < 2:
        await message.answer(
            "<b>⚠ Имя слишком короткое</b>",
            reply_markup=back_menu_kb("menu:cart"),
        )
        return
    await state.update_data(first_name=first_name)
    await state.set_state(CheckoutForm.last_name)
    await message.answer(
        "<b>📝 Фамилия</b>\n──────────────\n<i>Получателя</i>",
        reply_markup=back_menu_kb("menu:cart"),
    )


@router.message(CheckoutForm.last_name)
async def checkout_last_name(message: Message, state: FSMContext) -> None:
    last_name = (message.text or "").strip()
    if len(last_name) < 2:
        await message.answer(
            "<b>⚠ Фамилия слишком короткая</b>",
            reply_markup=back_menu_kb("menu:cart"),
        )
        return
    await state.update_data(last_name=last_name)
    await state.set_state(CheckoutForm.middle_name)
    await message.answer(
        "<b>📝 Отчество</b>\n──────────────\n<i>Получателя</i>",
        reply_markup=back_menu_kb("menu:cart"),
    )


@router.message(CheckoutForm.middle_name)
async def checkout_middle_name(message: Message, state: FSMContext) -> None:
    middle_name = (message.text or "").strip()
    if len(middle_name) < 2:
        await message.answer(
            "<b>⚠ Отчество слишком короткое</b>",
            reply_markup=back_menu_kb("menu:cart"),
        )
        return
    await state.update_data(middle_name=middle_name)
    await state.set_state(CheckoutForm.phone)
    await message.answer(
        "<b>📞 Телефон</b>\n──────────────\n<i>Мобильный получателя</i>",
        reply_markup=back_menu_kb("menu:cart"),
    )


@router.message(CheckoutForm.phone)
async def checkout_phone(message: Message, state: FSMContext) -> None:
    phone = (message.text or "").strip()
    if len(phone) < 7:
        await message.answer(
            "<b>⚠ Некорректный телефон</b>",
            reply_markup=back_menu_kb("menu:cart"),
        )
        return

    await state.update_data(phone=phone)
    await state.set_state(CheckoutForm.city)
    await message.answer(
        "<b>🏙 Город</b>\n──────────────\n<i>Место доставки (Новая почта)</i>",
        reply_markup=back_menu_kb("menu:cart"),
    )


@router.message(CheckoutForm.city)
async def checkout_city(message: Message, state: FSMContext) -> None:
    city = (message.text or "").strip()
    if len(city) < 2:
        await message.answer(
            "<b>⚠ Укажите город</b>",
            reply_markup=back_menu_kb("menu:cart"),
        )
        return
    await state.update_data(city=city)
    await state.set_state(CheckoutForm.branch)
    await message.answer(
        "<b>📮 Отделение Новой почты</b>\n──────────────\n<i>Номер или название отделения</i>",
        reply_markup=back_menu_kb("menu:cart"),
    )


@router.message(CheckoutForm.branch)
async def checkout_branch(message: Message, state: FSMContext) -> None:
    branch = (message.text or "").strip()
    if len(branch) < 1:
        await message.answer(
            "<b>⚠ Нужен номер отделения</b>",
            reply_markup=back_menu_kb("menu:cart"),
        )
        return

    await state.update_data(branch=branch)
    await state.set_state(CheckoutForm.payment)
    await message.answer(
        "<b>💳 Оплата</b>\n──────────────\n<i>Выберите способ</i>",
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

    if delivery_key == "city" and not is_within_business_hours():
        hs, he = get_business_hours_bounds()
        await callback.answer(
            f"Доставка по городу недоступна вне {hs}–{he}. Оформите позже или выберите другой способ доставки.",
            show_alert=True,
        )
        return

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
    uid = callback.from_user.id
    promo_off_chk, promo_err_chk, promo_code_chk = promo_discount_for_user_cart(uid)
    if promo_code_chk and promo_err_chk:
        clear_user_applied_promo(uid)
        await callback.answer(promo_err_chk, show_alert=True)
        return

    bonus = get_user_bonus(uid)
    await state.update_data(
        checkout_payment_key=key,
        checkout_payment=payment,
        checkout_full_name=full_name,
        checkout_phone=phone,
        checkout_delivery_address=delivery_address,
    )

    if bonus > 0:
        cart_sum = cart_total(uid)
        pr_off, _, _ = promo_discount_for_user_cart(uid)
        after_promo = max(1, cart_sum - pr_off)
        max_bonus_to_apply = max(0, after_promo - 1)
        bonus_to_apply = min(bonus, max_bonus_to_apply)

        if bonus_to_apply > 0:
            promo_line = ""
            if pr_off > 0:
                promo_line = f"🏷 Скидка по промокоду: <b>−{pr_off} грн</b>\n"
            await state.set_state(CheckoutForm.bonus_confirm)
            await _safe_edit(
                callback.message,
                f"🎁 У вас есть бонус: <b>{bonus} грн</b>\n"
                f"Сумма корзины: <b>{cart_sum} грн</b>\n"
                f"{promo_line}"
                f"К оплате (до бонуса): <b>{after_promo} грн</b>\n"
                f"Будет применено: <b>{bonus_to_apply} грн</b>\n"
                f"Итого к оплате: <b>{after_promo - bonus_to_apply} грн</b>\n\n"
                "Использовать бонус?",
                reply_markup=checkout_bonus_kb(bonus_to_apply),
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
    delivery_key = str(data.get("checkout_delivery_key") or "")
    user_id = callback.from_user.id

    if delivery_key == "city" and not is_within_business_hours():
        hs, he = get_business_hours_bounds()
        await state.clear()
        await callback.answer(
            f"Доставка по городу с {hs} до {he}. Сейчас нерабочее время — заказ не создан.",
            show_alert=True,
        )
        return

    cart_sum = cart_total(user_id)
    promo_off, promo_err, promo_code = promo_discount_for_user_cart(user_id)
    if promo_code and promo_err:
        clear_user_applied_promo(user_id)
        await state.clear()
        await callback.answer(promo_err, show_alert=True)
        return
    if promo_err or not promo_code:
        promo_off = 0
        promo_code = ""

    after_promo = max(1, cart_sum - promo_off)
    available_bonus = get_user_bonus(user_id) if use_bonus else 0
    max_bonus_to_apply = max(0, after_promo - 1)
    applied_bonus = min(available_bonus, max_bonus_to_apply)

    ok, payload = create_order_from_cart(
        user_id,
        name=full_name,
        phone=phone,
        address=delivery_address,
        delivery=delivery,
        payment=payment,
        discount=applied_bonus,
        promo_discount=promo_off,
        promo_code=promo_code if promo_off > 0 else "",
    )
    await state.clear()

    if not ok:
        await callback.answer(payload, show_alert=True)
        return

    if use_bonus and applied_bonus > 0:
        set_user_bonus(user_id, available_bonus - applied_bonus)

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
    bonus_line = f"\n🎁 Бонус применён: <b>-{applied_bonus} грн</b>" if use_bonus and applied_bonus > 0 else ""
    promo_line_ok = ""
    if order and order.get("promo_code"):
        promo_line_ok = f"\n🏷 Промокод: <b>{order['promo_code']}</b>"
    total_line = f"\nСумма к оплате: <b>{order['total']} грн</b>" if order else ""
    await _safe_edit(
        callback.message,
        f"✅ <b>Заказ оформлен</b>\n"
        "──────────────\n"
        f"📋 Номер: <code>{payload}</code>{total_line}{promo_line_ok}{bonus_line}{payment_info}",
        reply_markup=order_detail_kb(payload, back_target="menu:orders", can_send_receipt=can_send_receipt),
    )
    await callback.answer("✅ Готово!")


@router.callback_query(CheckoutForm.bonus_confirm, F.data == "shop:bonus:use")
async def checkout_bonus_use(callback: CallbackQuery, state: FSMContext) -> None:
    await _finalize_checkout(callback, state, use_bonus=True)


@router.callback_query(CheckoutForm.bonus_confirm, F.data == "shop:bonus:skip")
async def checkout_bonus_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await _finalize_checkout(callback, state, use_bonus=False)


@router.callback_query(F.data.startswith("shop:rate:"))
async def product_rate(callback: CallbackQuery, state: FSMContext) -> None:
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
        await state.set_state(ReviewTextForm.text)
        await state.update_data(review_order_id=order_id, review_product_id=product_id)
        await callback.message.answer(
            f"⭐ Оценка <b>{stars}/5</b> сохранена.\n\n"
            "✏ Напишите короткий отзыв или отправьте «—», чтобы пропустить.",
            reply_markup=back_menu_kb("menu:orders"),
        )
        await callback.answer("Сохранено")
    else:
        try:
            await callback.message.delete()
        except Exception:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        await callback.answer("Вы уже оценили этот товар", show_alert=True)


@router.message(ReviewTextForm.text)
async def review_text_save(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    order_id = str(data.get("review_order_id") or "")
    product_id = int(data.get("review_product_id") or 0)
    if not order_id or product_id < 1:
        await state.clear()
        return
    update_product_rating_comment(order_id, product_id, message.text or "")
    await state.clear()
    await message.answer(
        "<b>✅ Спасибо за отзыв!</b>",
        reply_markup=back_menu_kb("menu:orders"),
    )



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
    promo_ln = ""
    if order.get("promo_code"):
        promo_ln = f"🏷 Промокод: <b>{order['promo_code']}</b>\n"
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
            f"{promo_ln}"
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
            f"{promo_ln}"
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
        "<b>🧾 Отправка чека</b>\n"
        "──────────────\n"
        "Пришлите <b>фото</b> экрана оплаты или <b>PDF</b>.\n\n"
        "<i>Сжатый снимок экрана тоже подойдёт</i>",
        reply_markup=back_menu_kb(f"shop:order:{order_id}"),
    )
    await callback.answer()


@router.message(OrderReceiptForm.file, F.photo)
async def order_receipt_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    order_id = str(data.get("receipt_order_id", "")).strip()
    if not order_id:
        await state.clear()
        await message.answer(
            "<b>❌ Ошибка</b>\n(<i>не удалось привязать чек к заказу</i>)",
            reply_markup=back_menu_kb("menu:orders"),
        )
        return

    file_id = message.photo[-1].file_id
    ok = save_order_receipt(order_id, file_id=file_id, file_type="photo")
    if not ok:
        await state.clear()
        await message.answer(
            "<b>⏳ Чек уже отправлен</b>\n──────────────\n<i>Ожидайте проверки магазином</i>",
            reply_markup=back_menu_kb(f"shop:order:{order_id}"),
        )
        return

    order = get_order(order_id)
    caption = (
        f"<b>🧾 Чек от клиента</b>\n"
        "──────────────\n"
        f"📦 Заказ: <code>{order_id}</code>\n"
        f"👤 Клиент: <code>{message.from_user.id}</code>\n"
        f"💳 Оплата: <b>{order['payment'] if order else '-'}</b>"
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
    await message.answer(
        "<b>✅ Чек отправлен</b>\n"
        "──────────────\n"
        "<i>Скоро проверим и обновим статус заказа</i>",
        reply_markup=back_menu_kb(f"shop:order:{order_id}"),
    )


@router.message(OrderReceiptForm.file, F.document)
async def order_receipt_pdf(message: Message, state: FSMContext) -> None:
    doc = message.document
    is_pdf = bool(doc and ((doc.mime_type or "").lower() == "application/pdf" or (doc.file_name or "").lower().endswith(".pdf")))
    data = await state.get_data()
    order_fallback = str(data.get("receipt_order_id", "") or "").strip()
    back_ord = f"shop:order:{order_fallback}" if order_fallback else "menu:orders"
    if not is_pdf:
        await message.answer(
            "<b>⚠ Нужен PDF или фото</b>\n──────────────\n<i>Пришлите скрин или документ .pdf</i>",
            reply_markup=back_menu_kb(back_ord),
        )
        return

    order_id = order_fallback
    if not order_id:
        await state.clear()
        await message.answer(
            "<b>❌ Ошибка</b>\n(<i>не удалось привязать к заказу</i>)",
            reply_markup=back_menu_kb("menu:orders"),
        )
        return

    ok = save_order_receipt(order_id, file_id=doc.file_id, file_type="pdf")
    if not ok:
        await state.clear()
        await message.answer(
            "<b>⏳ Чек уже отправлен</b>\n──────────────\n<i>Ожидайте проверки</i>",
            reply_markup=back_menu_kb(f"shop:order:{order_id}"),
        )
        return

    order = get_order(order_id)
    caption = (
        f"<b>🧾 Чек от клиента</b>\n"
        "──────────────\n"
        f"📦 Заказ: <code>{order_id}</code>\n"
        f"👤 Клиент: <code>{message.from_user.id}</code>\n"
        f"💳 Оплата: <b>{order['payment'] if order else '-'}</b>"
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
    await message.answer(
        "<b>✅ Чек отправлен</b>\n"
        "──────────────\n"
        "<i>Скоро проверим и обновим статус</i>",
        reply_markup=back_menu_kb(f"shop:order:{order_id}"),
    )


@router.message(OrderReceiptForm.file)
async def order_receipt_invalid(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    oid = str(data.get("receipt_order_id", "") or "").strip()
    await message.answer(
        "<b>⚠ Нужен чек</b>\n──────────────\n<i>Фото или файл PDF</i>",
        reply_markup=back_menu_kb(f"shop:order:{oid}" if oid else "menu:orders"),
    )


@router.callback_query(F.data == "profile:edit")
async def profile_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileForm.first_name)
    await _safe_edit(
        callback.message,
        "<b>✏ Данные профиля</b>\n──────────────\n👤 <i>Ваше имя:</i>",
        reply_markup=back_menu_kb("menu:profile"),
    )
    await callback.answer()


@router.message(ProfileForm.first_name)
async def profile_first_name_save(message: Message, state: FSMContext) -> None:
    first_name = (message.text or "").strip()
    if len(first_name) < 2:
        await message.answer(
            "<b>⚠ Имя слишком короткое</b>",
            reply_markup=back_menu_kb("menu:profile"),
        )
        return
    await state.update_data(first_name=first_name)
    await state.set_state(ProfileForm.last_name)
    await message.answer(
        "<b>📝 Фамилия</b>",
        reply_markup=back_menu_kb("menu:profile"),
    )


@router.message(ProfileForm.last_name)
async def profile_last_name_save(message: Message, state: FSMContext) -> None:
    last_name = (message.text or "").strip()
    if len(last_name) < 2:
        await message.answer(
            "<b>⚠ Фамилия слишком короткая</b>",
            reply_markup=back_menu_kb("menu:profile"),
        )
        return
    await state.update_data(last_name=last_name)
    await state.set_state(ProfileForm.middle_name)
    await message.answer(
        "<b>📝 Отчество</b>",
        reply_markup=back_menu_kb("menu:profile"),
    )


@router.message(ProfileForm.middle_name)
async def profile_middle_name_save(message: Message, state: FSMContext) -> None:
    middle_name = (message.text or "").strip()
    if len(middle_name) < 2:
        await message.answer(
            "<b>⚠ Отчество слишком короткое</b>",
            reply_markup=back_menu_kb("menu:profile"),
        )
        return
    await state.update_data(middle_name=middle_name)
    await state.set_state(ProfileForm.phone)
    await message.answer(
        "<b>📞 Телефон</b>\n──────────────\n<i>Контакт для связи</i>",
        reply_markup=back_menu_kb("menu:profile"),
    )


@router.message(ProfileForm.phone)
async def profile_phone_save(message: Message, state: FSMContext) -> None:
    phone = (message.text or "").strip()
    if len(phone) < 7:
        await message.answer(
            "<b>⚠ Некорректный телефон</b>",
            reply_markup=back_menu_kb("menu:profile"),
        )
        return
    await state.update_data(phone=phone)
    await state.set_state(ProfileForm.city)
    await message.answer(
        "<b>🏙 Город</b>\n──────────────\n<i>Для Новой почты</i>",
        reply_markup=back_menu_kb("menu:profile"),
    )


@router.message(ProfileForm.city)
async def profile_city_save(message: Message, state: FSMContext) -> None:
    city = (message.text or "").strip()
    if len(city) < 2:
        await message.answer(
            "<b>⚠ Укажите город</b>",
            reply_markup=back_menu_kb("menu:profile"),
        )
        return
    await state.update_data(city=city)
    await state.set_state(ProfileForm.branch)
    await message.answer(
        "<b>📮 Отделение Новой почты</b>",
        reply_markup=back_menu_kb("menu:profile"),
    )


@router.message(ProfileForm.branch)
async def profile_branch_save(message: Message, state: FSMContext) -> None:
    branch = (message.text or "").strip()
    if len(branch) < 1:
        await message.answer(
            "<b>⚠ Нужен номер отделения</b>",
            reply_markup=back_menu_kb("menu:profile"),
        )
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
    await message.answer(
        "<b>✅ Профиль сохранён</b>\n──────────────\n<i>Данные можно изменить снова в любой момент</i>",
        reply_markup=profile_actions_inline_kb,
    )


@router.callback_query(F.data == "admin:welcome:edit")
async def admin_welcome_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_privileged(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(AdminWelcome.text)
    await _safe_edit(
        callback.message,
        "<b>✏ Приветствие</b>\n──────────────\n<i>Текст, который увидит клиент по /start</i>",
        reply_markup=back_admin_kb("admin:section:appearance"),
    )
    await callback.answer()


@router.message(AdminWelcome.text)
async def admin_welcome_text(message: Message, state: FSMContext) -> None:
    if not _is_privileged(message.from_user.id):
        await state.clear()
        return
    await state.update_data(welcome_text=(message.text or "").strip())
    await state.set_state(AdminWelcome.photo)
    await message.answer(
        "<b>🖼 Картинка к приветствию</b>\n──────────────\n<i>Фото или «-» только текст</i>",
        reply_markup=back_admin_kb("admin:section:appearance"),
    )


@router.message(AdminWelcome.photo, F.photo)
async def admin_welcome_photo(message: Message, state: FSMContext) -> None:
    if not _is_privileged(message.from_user.id):
        await state.clear()
        return
    data = await state.get_data()
    set_welcome_message(data.get("welcome_text", DEFAULT_SHOP_MENU_CAPTION), message.photo[-1].file_id)
    await state.clear()
    await message.answer(
        "<b>✅ Приветствие сохранено</b>\n──────────────\n<i>С фотографией</i>",
        reply_markup=back_admin_kb("admin:section:appearance"),
    )


@router.message(AdminWelcome.photo)
async def admin_welcome_no_photo(message: Message, state: FSMContext) -> None:
    if not _is_privileged(message.from_user.id):
        await state.clear()
        return
    if (message.text or "").strip() != "-":
        await message.answer(
            "<b>⚠ Нужно фото или «-»</b>",
            reply_markup=back_admin_kb("admin:section:appearance"),
        )
        return

    data = await state.get_data()
    set_welcome_message(data.get("welcome_text", DEFAULT_SHOP_MENU_CAPTION), "")
    await state.clear()
    await message.answer(
        "<b>✅ Приветствие сохранено</b>\n──────────────\n<i>Только текст</i>",
        reply_markup=back_admin_kb("admin:section:appearance"),
    )


@router.callback_query(F.data == "admin:main_menu:edit")
async def admin_main_menu_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_privileged(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(AdminMainMenu.text)
    await _safe_edit(
        callback.message,
        "<b>✏ Главное меню</b>\n──────────────\n<i>Текст, который увидит пользователь в главном меню</i>",
        reply_markup=back_admin_kb("admin:section:appearance"),
    )
    await callback.answer()


@router.message(AdminMainMenu.text)
async def admin_main_menu_text(message: Message, state: FSMContext) -> None:
    if not _is_privileged(message.from_user.id):
        await state.clear()
        return
    await state.update_data(main_menu_text=(message.text or "").strip())
    await state.set_state(AdminMainMenu.photo)
    await message.answer(
        "<b>🖼 Картинка к меню</b>\n──────────────\n<i>Фото или «-» только текст</i>",
        reply_markup=back_admin_kb("admin:section:appearance"),
    )


@router.message(AdminMainMenu.photo, F.photo)
async def admin_main_menu_photo(message: Message, state: FSMContext) -> None:
    if not _is_privileged(message.from_user.id):
        await state.clear()
        return
    data = await state.get_data()
    set_main_menu_message(data.get("main_menu_text", DEFAULT_SHOP_MENU_CAPTION), message.photo[-1].file_id)
    await state.clear()
    await message.answer(
        "<b>✅ Главное меню сохранено</b>\n──────────────\n<i>С фотографией</i>",
        reply_markup=back_admin_kb("admin:section:appearance"),
    )


@router.message(AdminMainMenu.photo)
async def admin_main_menu_no_photo(message: Message, state: FSMContext) -> None:
    if not _is_privileged(message.from_user.id):
        await state.clear()
        return
    if (message.text or "").strip() != "-":
        await message.answer(
            "<b>⚠ Нужно фото или «-»</b>",
            reply_markup=back_admin_kb("admin:section:appearance"),
        )
        return

    data = await state.get_data()
    set_main_menu_message(data.get("main_menu_text", DEFAULT_SHOP_MENU_CAPTION), "")
    await state.clear()
    await message.answer(
        "<b>✅ Главное меню сохранено</b>\n──────────────\n<i>Только текст</i>",
        reply_markup=back_admin_kb("admin:section:appearance"),
    )


@router.callback_query(F.data == "admin:shop")
async def admin_shop(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    vid = callback.from_user.id
    await _safe_edit(
        callback.message,
        _admin_shop_screen_text(vid),
        reply_markup=_admin_shop_markup(vid),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:section:catalog")
async def admin_section_catalog(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await _safe_edit(
        callback.message,
        ui_screen(
            emoji="🛍",
            title="Каталог и заказы",
            intro="Витрина и обработка заказов в одном блоке.",
            groups=[
                ("📦", "Товары и категории", "Цены, остатки, фото и структура каталога"),
                ("📋", "Заказы", "Новые, в работе, архив"),
                ("🧾", "Чеки клиентов", "Проверка оплат по фото и PDF"),
            ],
        ),
        reply_markup=admin_section_catalog_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:section:appearance")
async def admin_section_appearance(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await _safe_edit(
        callback.message,
        ui_screen(
            emoji="🎨",
            title="Оформление магазина",
            intro="То, что клиент видит при старте и в главном меню.",
            groups=[
                ("📝", "Приветствие /start", "Текст и фото на экране запуска"),
                ("🏠", "Главное меню", "Текст и опциональное изображение меню"),
            ],
        ),
        reply_markup=admin_section_appearance_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:section:payments")
async def admin_section_payments(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await _safe_edit(
        callback.message,
        ui_screen(
            emoji="💳",
            title="Платежи и доставка",
            intro="Настройте приём оплаты и доступные способы получения заказа.",
            groups=[
                ("💰", "Способы оплаты", "Наложка, карта, Apple Pay и Google Pay"),
                ("🏦", "Реквизиты", "Тексты для экрана оплаты клиента"),
                ("🚚", "Доставка", "Новая почта, город, самовывоз — вкл/выкл"),
            ],
        ),
        reply_markup=admin_section_payments_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:section:insights")
async def admin_section_insights(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await _safe_edit(
        callback.message,
        ui_screen(
            emoji="📊",
            title="Информация и статистика",
            intro="Сводки по магазину и работа с клиентской базой.",
            groups=[
                ("📰", "О боте", "Системные ID и ключевые цифры"),
                ("📈", "Метрики", "Сводка за неделю и развёрнутая статистика"),
                ("👥", "Клиенты", "Список покупателей и карточки"),
            ],
        ),
        reply_markup=admin_section_insights_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:section:io")
async def admin_section_io(callback: CallbackQuery) -> None:
    if not _is_privileged(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await _safe_edit(
        callback.message,
        ui_screen(
            emoji="📦",
            title="Экспорт и импорт",
            intro="Файлы для Excel и резервные копии каталога.",
            groups=[
                ("📥", "Заказы CSV", "Выгрузка таблицы с промокодами"),
                ("📤", "Каталог JSON", "Полный экспорт и импорт витрины"),
            ],
        ),
        reply_markup=admin_section_io_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:section:team")
async def admin_section_team(callback: CallbackQuery) -> None:
    if not _is_privileged(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await _safe_edit(
        callback.message,
        ui_screen(
            emoji="👨‍💼",
            title="Команда и промо",
            intro="Кто управляет магазином и как привлекать клиентов.",
            groups=[
                ("🛡", "Администраторы", "Права, менеджеры и техподдержка"),
                ("📣", "Рассылка", "Одно сообщение всем клиентам бота"),
                ("🏷", "Промокоды", "Процент или сумма скидки, лимиты активаций"),
            ],
        ),
        reply_markup=admin_section_team_kb(can_manage_admins=_is_owner(callback.from_user.id)),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:delivery:settings")
async def admin_delivery_settings(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    ds = get_delivery_settings()
    await _safe_edit(
        callback.message,
        _admin_delivery_settings_caption(),
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
        _admin_delivery_settings_caption(),
        reply_markup=admin_delivery_settings_kb(nova=ds["nova"], city=ds["city"], pickup=ds["pickup"]),
    )
    await callback.answer("✅ Обновлено")


# ─── Экспорт / Импорт каталога ───────────────────────────────────────────────

@router.callback_query(F.data == "admin:catalog:export")
async def admin_catalog_export(callback: CallbackQuery) -> None:
    if not _is_privileged(callback.from_user.id):
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
    if not _is_privileged(callback.from_user.id):
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
    if not _is_privileged(message.from_user.id):
        return

    doc = message.document
    if not doc.file_name or not doc.file_name.endswith(".json"):
        await message.answer(
            "<b>❌ Нужен .json</b>\n──────────────\n"
            "<i>Файл <code>catalog_export.json</code> из экспорта</i>",
            reply_markup=back_admin_kb("admin:shop"),
        )
        return

    try:
        file_info = await message.bot.get_file(doc.file_id)
        downloaded = await message.bot.download_file(file_info.file_path)
        raw = downloaded.read()
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        await message.answer(
            f"<b>❌ Не прочитать файл</b>\n──────────────\n<code>{e}</code>",
            reply_markup=back_admin_kb("admin:shop"),
        )
        await state.clear()
        return

    if data.get("version") != 1 or "categories" not in data:
        await message.answer(
            "<b>❌ Неверный формат</b>\n──────────────\n"
            "<i>Ожидается экспорт версии 1 с блоком <code>categories</code></i>",
            reply_markup=back_admin_kb("admin:shop"),
        )
        await state.clear()
        return

    try:
        cats, prods = import_catalog(data)
    except Exception as e:
        await message.answer(
            f"<b>❌ Импорт не выполнен</b>\n──────────────\n<code>{e}</code>",
            reply_markup=back_admin_kb("admin:shop"),
        )
        await state.clear()
        return

    await state.clear()
    await message.answer(
        f"<b>✅ Импорт готов</b>\n"
        "──────────────\n"
        f"📂 Категорий: <b>{cats}</b>\n"
        f"📦 Товаров: <b>{prods}</b>",
        reply_markup=back_admin_kb("admin:shop"),
    )


@router.message(AdminCatalogImport.file)
async def admin_catalog_import_wrong(message: Message, _state: FSMContext) -> None:
    if not _is_privileged(message.from_user.id):
        return
    await message.answer(
        "<b>📥 Импорт каталога</b>\n"
        "──────────────\n"
        "❌ Пришлите документ <code>.json</code>",
        reply_markup=back_admin_kb("admin:shop"),
    )


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
    await _safe_edit(callback.message, "📂 Введите название новой категории:", reply_markup=back_admin_kb("admin:categories"))
    await callback.answer()


@router.message(AdminCategory.name)
async def admin_category_add_finish(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    ok, text, _category_id = create_category((message.text or "").strip())
    if not ok:
        await message.answer(
            f"<b>⚠ Категория</b>\n──────────────\n{text}",
            reply_markup=back_admin_kb("admin:categories"),
        )
        return

    await state.clear()
    await message.answer(
        f"<b>✅ Готово</b>\n──────────────\n{text}",
        reply_markup=back_admin_kb("admin:categories"),
    )


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
    await _safe_edit(
        callback.message,
        "<b>📝 Название товара</b>\n──────────────\n<i>Как увидит клиент</i>",
        reply_markup=back_admin_kb("admin:categories"),
    )
    await callback.answer()


@router.message(AdminAddProduct.name)
async def admin_add_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=(message.text or "").strip())
    await state.set_state(AdminAddProduct.price)
    await message.answer(
        "<b>💰 Цена</b>\n──────────────\n<i>Целое число, гривны</i>",
        reply_markup=back_admin_kb("admin:section:catalog"),
    )


@router.message(AdminAddProduct.price)
async def admin_add_price(message: Message, state: FSMContext) -> None:
    if not (message.text or "").isdigit():
        await message.answer(
            "<b>⚠ Нужно число</b>\n(<i>цена в грн</i>)",
            reply_markup=back_admin_kb("admin:section:catalog"),
        )
        return
    await state.update_data(price=int(message.text))
    await state.set_state(AdminAddProduct.description)
    await message.answer(
        "<b>📄 Описание</b>\n──────────────\n<i>Текст в карточке</i>",
        reply_markup=back_admin_kb("admin:section:catalog"),
    )


@router.message(AdminAddProduct.description)
async def admin_add_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=(message.text or "").strip())
    await state.set_state(AdminAddProduct.stock)
    await message.answer(
        "<b>📦 Остаток</b>\n──────────────\n<i>Штук на складе</i>",
        reply_markup=back_admin_kb("admin:section:catalog"),
    )


@router.message(AdminAddProduct.stock)
async def admin_add_stock(message: Message, state: FSMContext) -> None:
    if not (message.text or "").isdigit():
        await message.answer(
            "<b>⚠ Нужно целое число</b>",
            reply_markup=back_admin_kb("admin:section:catalog"),
        )
        return
    await state.update_data(stock=int(message.text))
    await state.set_state(AdminAddProduct.photo)
    await message.answer(
        "<b>🖼 Фото</b>\n──────────────\n<i>Или «-» без изображения</i>",
        reply_markup=back_admin_kb("admin:section:catalog"),
    )


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
    await message.answer(
        f"<b>✅ Товар в каталоге</b>\n──────────────\n🆔 <code>{product_id}</code>",
        reply_markup=back_admin_kb("admin:product:list"),
    )


@router.message(AdminAddProduct.photo)
async def admin_add_no_photo(message: Message, state: FSMContext) -> None:
    if (message.text or "").strip() != "-":
        await message.answer(
            "<b>⚠ Нужно фото или «-»</b>",
            reply_markup=back_admin_kb("admin:section:catalog"),
        )
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
    await message.answer(
        f"<b>✅ Товар в каталоге</b>\n──────────────\n🆔 <code>{product_id}</code>",
        reply_markup=back_admin_kb("admin:product:list"),
    )


@router.callback_query(F.data == "admin:product:list")
async def admin_products(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    products = get_admin_products()
    if not products:
        await _safe_edit(
            callback.message,
            "<b>📦 Товары</b>\n──────────────\n<i>Пока пусто — добавьте из админки</i>",
            reply_markup=_admin_shop_markup(callback.from_user.id),
        )
        await callback.answer()
        return

    await _safe_edit(callback.message, "📦 <b>Товары</b>", reply_markup=admin_products_kb(products))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:product:view:"))
async def admin_product_view(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":")[-1])
    product = get_product(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    text = (
        f"📦 <b>{product['name']}</b>\n"
        f"🆔 ID: <code>{product['id']}</code>\n"
        f"💰 Цена: <b>{product['price']} грн</b>\n"
        f"📊 Остаток: <b>{product['stock']} шт</b>\n"
        f"📂 Категория: <b>{product['category_name']}</b>\n\n"
        f"{product['description']}"
    )
    await _safe_edit(callback.message, text, reply_markup=admin_product_actions_kb(product_id))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:product:price:"))
async def admin_edit_price_start(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[-1])
    await state.set_state(AdminEditProduct.price)
    await state.update_data(edit_product_id=product_id)
    await _safe_edit(
        callback.message,
        "<b>💰 Новая цена</b>\n──────────────\n<i>Гривны, целое число</i>",
        reply_markup=back_admin_kb("admin:product:list"),
    )
    await callback.answer()


@router.message(AdminEditProduct.price)
async def admin_edit_price(message: Message, state: FSMContext) -> None:
    if not (message.text or "").isdigit():
        await message.answer(
            "<b>⚠ Нужно число</b>",
            reply_markup=back_admin_kb("admin:product:list"),
        )
        return
    data = await state.get_data()
    update_product(int(data["edit_product_id"]), price=int(message.text))
    await state.clear()
    await message.answer(
        "<b>✅ Цена сохранена</b>",
        reply_markup=back_admin_kb("admin:product:list"),
    )


@router.callback_query(F.data.startswith("admin:product:stock:"))
async def admin_edit_stock_start(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[-1])
    await state.set_state(AdminEditProduct.stock)
    await state.update_data(edit_product_id=product_id)
    await _safe_edit(
        callback.message,
        "<b>📊 Новый остаток</b>\n──────────────\n<i>Штуки на складе</i>",
        reply_markup=back_admin_kb("admin:product:list"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:product:desc:"))
async def admin_edit_desc_start(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[-1])
    await state.set_state(AdminEditProduct.description)
    await state.update_data(edit_product_id=product_id)
    await _safe_edit(
        callback.message,
        "<b>📝 Новое описание</b>\n──────────────\n<i>Текст карточки товара (HTML допускается)</i>",
        reply_markup=back_admin_kb("admin:product:list"),
    )
    await callback.answer()


@router.message(AdminEditProduct.description, F.text)
async def admin_edit_description(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    pid = int(data["edit_product_id"])
    text = (message.text or "").strip()
    if not text:
        await message.answer(
            "<b>⚠ Пустой текст</b>",
            reply_markup=back_admin_kb("admin:product:list"),
        )
        return
    update_product(pid, description=text[:3500])
    await state.clear()
    await message.answer(
        "<b>✅ Описание сохранено</b>",
        reply_markup=back_admin_kb("admin:product:list"),
    )


@router.message(AdminEditProduct.stock)
async def admin_edit_stock(message: Message, state: FSMContext) -> None:
    if not (message.text or "").isdigit():
        await message.answer(
            "<b>⚠ Нужно число</b>",
            reply_markup=back_admin_kb("admin:product:list"),
        )
        return
    data = await state.get_data()
    pid = int(data["edit_product_id"])
    old_product = get_product(pid)
    old_stock = int(old_product["stock"]) if old_product else 0
    new_stock = int(message.text)
    update_product(pid, stock=new_stock)
    await state.clear()
    await message.answer(
        "<b>✅ Остаток сохранён</b>",
        reply_markup=back_admin_kb("admin:product:list"),
    )
    new_product = get_product(pid)
    if old_stock <= 0 and new_product and int(new_product["stock"]) > 0:
        title = new_product.get("name") or "Товар"
        notify_kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Открыть товар", callback_data=f"shop:product:{pid}")]]
        )
        for uid in wishlist_user_ids_for_product(pid):
            try:
                await message.bot.send_message(
                    int(uid),
                    f"❤️ В избранном снова в наличии: <b>{title}</b>",
                    reply_markup=notify_kb,
                )
            except Exception:
                pass


@router.callback_query(F.data.startswith("admin:product:photo:"))
async def admin_edit_photo_start(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[-1])
    await state.set_state(AdminEditProduct.photo)
    await state.update_data(edit_product_id=product_id)
    await _safe_edit(
        callback.message,
        "<b>🖼 Новое фото</b>\n──────────────\n<i>Пришлите изображение</i>",
        reply_markup=back_admin_kb("admin:section:catalog"),
    )
    await callback.answer()


@router.message(AdminEditProduct.photo, F.photo)
async def admin_edit_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    update_product(int(data["edit_product_id"]), photo=message.photo[-1].file_id)
    await state.clear()
    await message.answer(
        "<b>✅ Фото обновлено</b>",
        reply_markup=back_admin_kb("admin:section:catalog"),
    )


@router.callback_query(F.data.startswith("admin:product:delete:"))
async def admin_delete_product(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":")[-1])
    delete_product(product_id)
    await _safe_edit(
        callback.message,
        "<b>🗑 Товар удалён</b>\n──────────────\n<i>Из каталога убран</i>",
        reply_markup=_admin_shop_markup(callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:orders")
async def admin_orders(callback: CallbackQuery) -> None:
    orders = list_all_orders(limit=100)
    if not orders:
        await _safe_edit(
            callback.message,
            ui_panel(
                emoji="📋",
                title="Заказы",
                intro="Пока нет ни одного заказа — как только клиент оформит покупку, он появится здесь.",
                body_lines=["🛒 <i>Проверьте витрину и способы оплаты, если ожидали заказы раньше.</i>"],
            ),
            reply_markup=back_admin_kb("admin:section:catalog"),
        )
        await callback.answer()
        return

    has_new = any(o.get("status_raw", "") in _NEW_STATUSES for o in orders)
    has_inwork = any(o.get("status_raw", "") in _INWORK_STATUSES for o in orders)
    has_archive = any(o.get("status_raw", "") in _ARCHIVE_STATUSES for o in orders)
    await _safe_edit(
        callback.message,
        ui_screen(
            emoji="📋",
            title="Заказы",
            intro="Разделите поток по статусам или найдите заказ по чеку.",
            groups=[
                ("🔵", "Новые", "Только что оформленные и ожидающие обработки"),
                ("🔄", "В работе", "Оплаченные и отправленные"),
                ("📁", "Архив", "Доставленные и отменённые"),
                ("🧾", "Поиск по чеку", "Фильтр по статусу проверки оплаты"),
            ],
        ),
        reply_markup=admin_orders_menu_kb(has_new=has_new, has_inwork=has_inwork, has_archive=has_archive),
    )
    await callback.answer()


def _promos_admin_view() -> tuple[str, InlineKeyboardMarkup]:
    promos = list_promocodes()
    lines: list[str] = []
    kb_rows: list[list[InlineKeyboardButton]] = []
    for p in promos[:15]:
        kind_l = "%" if str(p["kind"]).lower() == "percent" else "грн"
        lim = "∞" if int(p["max_uses"]) < 0 else str(p["max_uses"])
        vu = p.get("valid_until") or "—"
        owner = int(p.get("target_user_id") or 0)
        owner_s = f", 👤 {owner}" if owner > 0 else ""
        st = "✅" if p["active"] else "⏸"
        code_s = str(p["code"])
        lines.append(
            f"{st} <code>{code_s}</code> — {p['value']}{kind_l}, исп. {p['used_count']}/{lim}{owner_s}, до <i>{vu}</i>"
        )
        pid = int(p["id"])
        kb_rows.append(
            [
                InlineKeyboardButton(text=f"↻ {code_s[:16]}", callback_data=f"admin:promo:t:{pid}"),
                InlineKeyboardButton(text="🗑", callback_data=f"admin:promo:d:{pid}"),
            ]
        )
    body = "\n".join(lines) if lines else "📭 <i>Промокодов пока нет — создайте первый кнопкой ниже.</i>"
    head = ui_panel(
        emoji="🏷",
        title="Промокоды",
        intro="Включение, лимиты и удаление. В строке кнопки ↻ и 🗑 управляют кодом.",
        body_lines=[],
    )
    text = f"{head}\n\n{body}"
    kb_rows.append([InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin:promo:add")])
    kb_rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="admin:shop")])
    return text, InlineKeyboardMarkup(inline_keyboard=kb_rows)


@router.callback_query(F.data == "admin:analytics")
async def admin_analytics(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    ax = get_analytics_extended()
    lines_sales = "\n".join(f"  ▸ {t[0]} · <b>{t[1]}</b> шт · <b>{t[2]}</b> грн" for t in ax["top_sales"]) or "  <i>— нет данных —</i>"
    lines_views = "\n".join(f"  ▸ {t[0]} · <b>{t[1]}</b> просм." for t in ax["top_views"]) or "  <i>— нет данных —</i>"
    text = ui_panel(
        emoji="📊",
        title="Сводка",
        intro="Срез за 7 дней по продажам и интерес к товарам (просмотры).",
        body_lines=[
            "📈 <b>Топ продаж</b> <i>(7 дней)</i>",
            lines_sales,
            "",
            "👁 <b>Топ просмотров</b> <i>(всё время)</i>",
            lines_views,
            "",
            f"🏷 <b>Заказов с промокодом (всего):</b> {ax['orders_with_promo']}",
        ],
    )
    await _safe_edit(callback.message, text, reply_markup=back_admin_kb("admin:section:insights"))
    await callback.answer()


@router.callback_query(F.data == "admin:orders:export")
async def admin_orders_export(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    raw = export_orders_csv().encode("utf-8-sig")
    file = BufferedInputFile(raw, filename="orders_export.csv")
    await callback.message.answer_document(
        file,
        caption="<b>📥 Экспорт заказов</b>\n<i>Разделитель ; для Excel</i>",
        reply_markup=back_admin_kb("admin:shop"),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:promos")
async def admin_promos_menu(callback: CallbackQuery) -> None:
    if not _is_privileged(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    text, markup = _promos_admin_view()
    await _safe_edit(callback.message, text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:promo:t:"))
async def admin_promo_toggle(callback: CallbackQuery) -> None:
    if not _is_privileged(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    row_id = int(callback.data.split(":")[-1])
    toggle_promocode_id(row_id)
    text, markup = _promos_admin_view()
    await _safe_edit(callback.message, text, reply_markup=markup)
    await callback.answer("Готово")


@router.callback_query(F.data.startswith("admin:promo:d:"))
async def admin_promo_delete(callback: CallbackQuery) -> None:
    if not _is_privileged(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    row_id = int(callback.data.split(":")[-1])
    delete_promocode_id(row_id)
    text, markup = _promos_admin_view()
    await _safe_edit(callback.message, text, reply_markup=markup)
    await callback.answer("Удалено")


@router.callback_query(F.data == "admin:promo:add")
async def admin_promo_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_privileged(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(AdminPromoCreate.line)
    await _safe_edit(
        callback.message,
        "<b>➕ Новый промокод</b>\n──────────────\n"
        "Одной строкой, примеры:\n"
        "<code>SALE10 percent 10</code>\n"
        "<code>GIFT500 fixed 500 max:100</code>\n"
        "<code>NY26 fixed 50 until:2026-12-31</code>\n"
        "<code>VIP30 percent 30 user:123456789</code>\n\n"
        "<i>percent — скидка %, fixed — грн; max — лимит активаций (−1 без лимита); until — срок ISO; user — Telegram ID клиента для персонального кода</i>",
        reply_markup=back_admin_kb("admin:promos"),
    )
    await callback.answer()


@router.message(AdminPromoCreate.line)
async def admin_promo_add_finish(message: Message, state: FSMContext) -> None:
    if not _is_privileged(message.from_user.id):
        await state.clear()
        return

    line = (message.text or "").strip()
    parts = line.split()
    if len(parts) < 3:
        await message.answer(
            "<b>⚠ Нужно минимум: КОД percent|fixed ЗНАЧЕНИЕ</b>",
            reply_markup=back_admin_kb("admin:promos"),
        )
        return
    code, kind_raw, val_raw = parts[0], parts[1].lower(), parts[2]
    if kind_raw not in {"percent", "fixed"} or not val_raw.isdigit():
        await message.answer("<b>⚠ Тип: percent или fixed; значение — целое число</b>", reply_markup=back_admin_kb("admin:promos"))
        return
    max_uses = -1
    valid_until = ""
    target_user_id = 0
    for extra in parts[3:]:
        el = extra.lower()
        if el.startswith("max:"):
            try:
                max_uses = int(extra.split(":", 1)[1])
            except ValueError:
                pass
        elif el.startswith("until:"):
            valid_until = extra.split(":", 1)[1].strip()
        elif el.startswith("user:") or el.startswith("uid:"):
            raw_user = extra.split(":", 1)[1].strip()
            if raw_user.isdigit():
                target_user_id = int(raw_user)
            else:
                await message.answer(
                    "<b>⚠ user должен быть числовым Telegram ID, пример: user:123456789</b>",
                    reply_markup=back_admin_kb("admin:promos"),
                )
                return

    ok, msg = create_promocode(
        code,
        kind_raw,
        int(val_raw),
        max_uses=max_uses,
        valid_until=valid_until,
        target_user_id=target_user_id,
    )
    await state.clear()
    if not ok:
        await message.answer(f"<b>❌ {msg}</b>", reply_markup=back_admin_kb("admin:promos"))
        return
    await message.answer(f"<b>✅ {msg}</b>", reply_markup=back_admin_kb("admin:promos"))


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
    pr = f"🏷 Промокод: <b>{order['promo_code']}</b>\n" if order.get("promo_code") else ""
    text = (
        f"<b>📦 Заказ {order_id}</b>\n"
        f"📌 Статус: <b>{order['status']}</b>\n"
        f"👤 Клиент: <b>{order['name']}</b>\n"
        f"📞 Телефон: <b>{order['phone']}</b>\n"
        f"📍 Адрес: <b>{order['address']}</b>\n"
        f"🚚 Доставка: <b>{order['delivery']}</b>\n"
        f"💳 Оплата: <b>{order['payment']}</b>\n"
        f"🧾 Чек: <b>{_receipt_status_text(order)}</b>\n"
        f"{pr}"
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
    pr = f"🏷 Промокод: <b>{order['promo_code']}</b>\n" if order.get("promo_code") else ""
    text = (
        f"<b>📦 Заказ {order_id}</b>\n"
        f"📌 Статус: <b>{order['status']}</b>\n"
        f"👤 Клиент: <b>{order['name']}</b>\n"
        f"📞 Телефон: <b>{order['phone']}</b>\n"
        f"📍 Адрес: <b>{order['address']}</b>\n"
        f"🚚 Доставка: <b>{order['delivery']}</b>\n"
        f"💳 Оплата: <b>{order['payment']}</b>\n"
        f"🧾 Чек: <b>{_receipt_status_text(order)}</b>\n"
        f"{pr}"
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

    if is_user_status_notification_enabled():
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


@router.callback_query(F.data.startswith("admin:users:list"))
async def admin_users_list(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    source = parts[3] if len(parts) > 3 else ""
    back_target = "admin:section:insights" if source == "insights" else "admin:shop"

    users = list_customer_users()
    if not users:
        await _safe_edit(callback.message, "👥 Клиентов пока нет", reply_markup=back_admin_kb(back_target))
        await callback.answer()
        return

    await _safe_edit(
        callback.message,
        "<b>👥 Клиенты</b>",
        reply_markup=admin_people_kb(users, back_target=back_target, source=source),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:admins:list")
async def admin_admins_list(callback: CallbackQuery) -> None:
    if not _is_privileged(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    admins = list_admin_users()
    await _safe_edit(
        callback.message,
        "<b>🛡 Админы</b>",
        reply_markup=admin_people_kb(admins, back_target="admin:section:team", add_admin_button=_is_owner(callback.from_user.id)),
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
        await message.answer(
            "⚠️ Нужен числовой Telegram ID",
            reply_markup=back_admin_kb("admin:admins:list"),
        )
        return

    target_user_id = int(raw_value)
    add_admin_user(target_user_id)
    await state.clear()
    await message.answer(
        f"✅ Пользователь <code>{target_user_id}</code> теперь админ.",
        reply_markup=back_admin_kb("admin:admins:list"),
    )


@router.callback_query(F.data.startswith("admin:user:view:"))
async def admin_user_view(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    target_user_id = int(parts[3])
    source = parts[4] if len(parts) > 4 else ""
    await _render_admin_user_card(callback.message, callback.from_user.id, target_user_id, source=source)
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


@router.callback_query(F.data.startswith("admin:user:manager:"))
async def admin_user_manager(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer("Только главный админ может назначать менеджеров", show_alert=True)
        return

    parts = callback.data.split(":")
    target_user_id = int(parts[3])
    source = parts[4] if len(parts) > 4 else ""
    set_user_role(target_user_id, "manager")
    await _render_admin_user_card(callback.message, callback.from_user.id, target_user_id, source=source)
    await callback.answer("Назначен менеджером магазина")


@router.callback_query(F.data.startswith("admin:user:demote:"))
async def admin_user_demote(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer("Только главный админ может управлять администраторами", show_alert=True)
        return

    parts = callback.data.split(":")
    target_user_id = int(parts[3])
    source = parts[4] if len(parts) > 4 else ""
    if not remove_admin_user(target_user_id):
        await callback.answer("Нельзя снять главного админа", show_alert=True)
        return

    await _render_admin_user_card(callback.message, callback.from_user.id, target_user_id, source=source)
    await callback.answer("Админ снят")


@router.callback_query(F.data.startswith("admin:user:support:enable:"))
async def admin_user_support_enable(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer("Только главный админ может назначать техподдержку", show_alert=True)
        return

    parts = callback.data.split(":")
    target_user_id = int(parts[4])
    source = parts[5] if len(parts) > 5 else ""
    set_support_admin(target_user_id, True)
    await _render_admin_user_card(callback.message, callback.from_user.id, target_user_id, source=source)
    await callback.answer("Назначен в техподдержку")


@router.callback_query(F.data.startswith("admin:user:support:disable:"))
async def admin_user_support_disable(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer("Только главный админ может назначать техподдержку", show_alert=True)
        return

    parts = callback.data.split(":")
    target_user_id = int(parts[4])
    source = parts[5] if len(parts) > 5 else ""
    set_support_admin(target_user_id, False)
    await _render_admin_user_card(callback.message, callback.from_user.id, target_user_id, source=source)
    await callback.answer("Убран из техподдержки")


@router.callback_query(F.data.startswith("admin:user:orders:"))
async def admin_user_orders(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    target_user_id = int(parts[3])
    source = parts[4] if len(parts) > 4 else ""
    back_to_card = f"admin:user:view:{target_user_id}:{source}" if source else f"admin:user:view:{target_user_id}"
    orders = get_user_orders(target_user_id)

    if not orders:
        text = f"<b>🛒 Покупки пользователя <code>{target_user_id}</code></b>\n\nПокупок нет."
        await _safe_edit(
            callback.message,
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅ Назад", callback_data=back_to_card)]
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
            [InlineKeyboardButton(text="⬅ Назад", callback_data=back_to_card)]
        ]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:user:bonus:"))
async def admin_user_bonus_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    target_user_id = int(parts[3])
    source = parts[4] if len(parts) > 4 else ""
    back_to_card = f"admin:user:view:{target_user_id}:{source}" if source else f"admin:user:view:{target_user_id}"
    current = get_user_bonus(target_user_id)
    await state.set_state(AdminUsers.bonus_amount)
    await state.update_data(bonus_target_user_id=target_user_id, bonus_source=source)
    await _safe_edit(
        callback.message,
        f"<b>🎁 Бонус клиента</b>\n"
        "──────────────\n"
        f"👤 <code>{target_user_id}</code>\n"
        f"💰 Сейчас: <b>{current} грн</b>\n\n"
        "<i>Новое значение (грн), <code>0</code> — обнулить:</i>",
        reply_markup=back_admin_kb(back_to_card),
    )
    await callback.answer()


@router.message(AdminUsers.bonus_amount)
async def admin_user_bonus_set(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    raw = (message.text or "").strip()
    if not raw.isdigit():
        data_err = await state.get_data()
        tid = int(data_err.get("bonus_target_user_id", 0) or 0)
        source = str(data_err.get("bonus_source", "") or "")
        back_to_card = f"admin:user:view:{tid}:{source}" if tid and source else (f"admin:user:view:{tid}" if tid else "admin:shop")
        await message.answer(
            "<b>⚠ Нужно целое число</b>\n(<i>например 150</i>)",
            reply_markup=back_admin_kb(back_to_card),
        )
        return

    amount = int(raw)
    data = await state.get_data()
    target_user_id = int(data.get("bonus_target_user_id", 0))
    source = str(data.get("bonus_source", "") or "")
    back_to_card = f"admin:user:view:{target_user_id}:{source}" if source else f"admin:user:view:{target_user_id}"
    back_to_list = f"admin:users:list:{source}" if source else "admin:section:insights"
    if not target_user_id:
        await state.clear()
        return

    set_user_bonus(target_user_id, amount)
    await state.clear()

    # Уведомляем пользователя о начислении/обновлении бонуса
    try:
        await message.bot.send_message(
            target_user_id,
            f"<b>🎁 Бонус обновлён</b>\n──────────────\n💰 <b>{amount} грн</b> на вашем счёте в профиле.",
            reply_markup=main_menu_inline_kb(is_admin=is_admin_user(target_user_id)),
        )
    except Exception:
        pass

    await message.answer(
        f"<b>✅ Бонус сохранён</b>\n──────────────\n"
        f"👤 <code>{target_user_id}</code> → <b>{amount} грн</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👤 К карточке", callback_data=back_to_card)],
                [InlineKeyboardButton(text="⬅ Назад", callback_data=back_to_list)],
            ]
        ),
    )


@router.callback_query(F.data.startswith("admin:user:msg:"))
async def admin_user_message_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    target_user_id = int(parts[3])
    source = parts[4] if len(parts) > 4 else ""
    back_to_card = f"admin:user:view:{target_user_id}:{source}" if source else f"admin:user:view:{target_user_id}"
    await state.set_state(AdminUsers.message_text)
    await state.update_data(target_user_id=target_user_id, message_back_target=back_to_card)
    await _safe_edit(
        callback.message,
        f"<b>✉ Сообщение клиенту</b>\n──────────────\n👤 <code>{target_user_id}</code>\n\n<i>Текст в ответ:</i>",
        reply_markup=back_admin_kb(back_to_card),
    )
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
    await _safe_edit(
        callback.message,
        f"<b>✉ Покупателю</b>\n──────────────\n📦 <code>{order_id}</code>\n\n<i>Текст сообщения:</i>",
        reply_markup=back_admin_kb(f"admin:order:view:{order_id}"),
    )
    await callback.answer()


@router.message(AdminUsers.message_text)
async def admin_user_message_send(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    data = await state.get_data()
    target_user_id = int(data.get("target_user_id", 0))
    back_target = str(data.get("message_back_target", "admin:shop"))

    if not text:
        await message.answer(
            "<b>⚠ Пустое сообщение</b>",
            reply_markup=back_admin_kb(back_target),
        )
        return

    await state.clear()

    if not target_user_id:
        await message.answer(
            "<b>❌ Нет получателя</b>",
            reply_markup=back_admin_kb("admin:shop"),
        )
        return

    user_kb = main_menu_inline_kb(is_admin=is_admin_user(target_user_id))
    try:
        await message.bot.send_message(
            target_user_id,
            f"<b>✉ Сообщение от магазина</b>\n──────────────\n{text}",
            reply_markup=user_kb,
        )
        await message.answer(
            f"<b>✅ Доставлено</b>\n──────────────\n👤 <code>{target_user_id}</code>",
            reply_markup=back_admin_kb(back_target),
        )
    except Exception:
        await message.answer(
            "<b>❌ Не доставлено</b>\n──────────────\n<i>Клиент не писал боту или заблокировал.</i>",
            reply_markup=back_admin_kb(back_target),
        )


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_privileged(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await state.set_state(AdminBroadcast.text)
    await _safe_edit(
        callback.message,
        "<b>📢 Рассылка</b>\n──────────────\n<i>Текст одним сообщением — уйдёт всем клиентам</i>",
        reply_markup=back_admin_kb(),
    )
    await callback.answer()


@router.message(AdminBroadcast.text)
async def admin_broadcast_send(message: Message, state: FSMContext) -> None:
    if not _is_privileged(message.from_user.id):
        await state.clear()
        return
    text = message.text or ""
    user_ids = get_all_user_ids_for_broadcast()
    sent = 0
    for uid in user_ids:
        try:
            await message.bot.send_message(
                uid,
                f"<b>📢 Сообщение магазина</b>\n──────────────\n{text}",
                reply_markup=main_menu_inline_kb(is_admin=is_admin_user(uid)),
            )
            sent += 1
        except Exception:
            pass
    await state.clear()
    await message.answer(
        f"<b>✅ Рассылка готова</b>\n──────────────\n📨 Дошло до <b>{sent}</b> адресатов",
        reply_markup=back_admin_kb("admin:shop"),
    )


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
        reply_markup=back_admin_kb("admin:section:insights"),
    )
    await callback.answer()


@router.callback_query(F.data == "shop:noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ============================================================================
# ТЕКСТОВЫЕ МЕНЮ
# ============================================================================

@router.callback_query(F.data == "admin:text_menus")
async def admin_text_menus_list(callback: CallbackQuery) -> None:
    if not _is_privileged(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    
    menus = get_text_menus()
    text = "<b>📋 Текстовые меню</b>\n──────────────\n"
    if menus:
        text += f"<i>Найдено меню: {len(menus)}</i>"
    else:
        text += "<i>没有меню. Создайте первое.</i>"
    
    await _safe_edit(
        callback.message,
        text,
        reply_markup=admin_text_menus_kb(menus),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:text_menu:new")
async def admin_text_menu_new(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_privileged(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    
    await state.set_state(AdminTextMenu.name)
    await _safe_edit(
        callback.message,
        "<b>➕ Создание меню</b>\n──────────────\n<i>Введите название меню</i>",
        reply_markup=admin_text_menu_cancel_kb(),
    )
    await callback.answer()


@router.message(AdminTextMenu.name)
async def admin_text_menu_name(message: Message, state: FSMContext) -> None:
    if not _is_privileged(message.from_user.id):
        await state.clear()
        return
    
    menu_name = (message.text or "").strip()
    if not menu_name:
        await message.answer(
            "<b>⚠ Введите название</b>",
            reply_markup=admin_text_menu_cancel_kb(),
        )
        return
    
    await state.update_data(menu_name=menu_name)
    await state.set_state(AdminTextMenu.text)
    await message.answer(
        "<b>✍ Текст меню</b>\n──────────────\n<i>Введите текстовое содержимое</i>",
        reply_markup=admin_text_menu_cancel_kb(),
    )


@router.message(AdminTextMenu.text)
async def admin_text_menu_text(message: Message, state: FSMContext) -> None:
    if not _is_privileged(message.from_user.id):
        await state.clear()
        return
    
    menu_text = (message.text or "").strip()
    if not menu_text:
        await message.answer(
            "<b>⚠ Введите текст</b>",
            reply_markup=admin_text_menu_cancel_kb(),
        )
        return
    
    await state.update_data(menu_text=menu_text)
    await state.set_state(AdminTextMenu.photo)
    await message.answer(
        "<b>🖼 Фото (опционально)</b>\n──────────────\n<i>Отправьте фото или напишите «-» для пропуска</i>",
        reply_markup=admin_text_menu_cancel_kb(),
    )


@router.message(AdminTextMenu.photo, F.photo)
async def admin_text_menu_photo(message: Message, state: FSMContext) -> None:
    if not _is_privileged(message.from_user.id):
        await state.clear()
        return
    
    data = await state.get_data()
    menu_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    
    set_text_menu(
        menu_id,
        data.get("menu_name", "Меню"),
        data.get("menu_text", ""),
        message.photo[-1].file_id,
    )
    
    await state.clear()
    await message.answer(
        "<b>✅ Меню сохранено с фото</b>",
        reply_markup=back_admin_kb("admin:text_menus"),
    )


@router.message(AdminTextMenu.photo)
async def admin_text_menu_no_photo(message: Message, state: FSMContext) -> None:
    if not _is_privileged(message.from_user.id):
        await state.clear()
        return
    
    if (message.text or "").strip() != "-":
        await message.answer(
            "<b>⚠ Отправьте фото или напишите «-»</b>",
            reply_markup=admin_text_menu_cancel_kb(),
        )
        return
    
    data = await state.get_data()
    menu_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    
    set_text_menu(
        menu_id,
        data.get("menu_name", "Меню"),
        data.get("menu_text", ""),
    )
    
    await state.clear()
    await message.answer(
        "<b>✅ Меню сохранено без фото</b>",
        reply_markup=back_admin_kb("admin:text_menus"),
    )


@router.callback_query(F.data.startswith("admin:text_menu:"))
async def admin_text_menu_view(callback: CallbackQuery) -> None:
    if not _is_privileged(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    
    parts = callback.data.split(":", maxsplit=2)
    if len(parts) < 3:
        await callback.answer("Ошибка", show_alert=True)
        return
    
    menu_id = parts[2]
    
    # Handle delete action
    if menu_id.startswith("delete:"):
        delete_menu_id = menu_id[7:]
        delete_text_menu(delete_menu_id)
        await callback.answer("✅ Меню удалено")
        await admin_text_menus_list(callback)
        return
    
    # Handle edit action
    if menu_id.startswith("edit:"):
        edit_menu_id = menu_id[5:]
        menu_data = get_text_menu(edit_menu_id)
        if not menu_data:
            await callback.answer("Меню не найдено", show_alert=True)
            return
        
        # For now, just show edit confirmation
        await callback.answer("Редактирование меню будет в следующей версии", show_alert=True)
        return
    
    # View menu
    menu_data = get_text_menu(menu_id)
    if not menu_data:
        await callback.answer("Меню не найдено", show_alert=True)
        return
    
    text = f"<b>📋 {menu_data['name']}</b>\n──────────────\n{menu_data['text']}"
    
    if menu_data.get("photo"):
        await callback.message.delete()
        await callback.bot.send_photo(
            chat_id=callback.from_user.id,
            photo=menu_data["photo"],
            caption=text,
            reply_markup=admin_text_menu_actions_kb(menu_id),
            parse_mode="HTML",
        )
    else:
        await _safe_edit(
            callback.message,
            text,
            reply_markup=admin_text_menu_actions_kb(menu_id),
        )
    
    await callback.answer()
