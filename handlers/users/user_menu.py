import datetime
import html
import os
import shutil
import sqlite3
import tempfile

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from data.config import adm, bot_description, get_default_menu_banner_path, username as bot_username
from loader import dispatcher
from keyboards.inline.shop_inline import (
    admin_staff_role_pick_kb,
    admin_staff_users_kb,
    staff_permissions_editor_kb,
)
from keyboards.inline.user_inline import (
    admin_business_hours_kb,
    admin_referral_kb,
    admin_settings_inline_kb,
    admin_settings_notifications_inline_kb,
    admin_settings_payments_inline_kb,
    admin_settings_service_inline_kb,
    admin_menu_inline_kb,
    admin_reply_cancel_kb,
    main_menu_inline_kb,
    profile_actions_inline_kb,
    support_back_inline_kb,
    support_menu_inline_kb,
    support_tickets_list_kb,
    support_ticket_view_kb,
)
from handlers.users.shop_state import (
    AdminBusinessHours,
    AdminDatabaseUpload,
    AdminNotifications,
    AdminPayments,
    AdminReferral,
    AdminStockAlerts,
    SupportDialog,
)
from utils.set_bot_commands import set_default_commands
from utils.db_api.shop import get_user_profile as get_shop_user_profile
from utils.db_api.shop import apply_referral_from_start_payload, ensure_user, get_or_create_referral_code
from utils.db_api.shop import (
    get_admin_ids,
    get_admin_new_order_template,
    get_notify_chat_id,
    get_payment_info,
    get_cryptobot_token,
    get_low_stock_threshold,
    get_support_admin_ids,
    get_shop_setting,
    get_shop_stats,
    get_start_command_description,
    get_user_status_template,
    get_welcome_message,
    get_main_menu_message,
    init_shop_tables,
    get_effective_staff_permissions,
    staff_has_perm,
    list_staff_by_roles,
    toggle_staff_perm_for_user,
    is_admin_user,
    is_payment_enabled,
    is_maintenance,
    is_owner_user,
    is_privileged_admin,
    toggle_maintenance,
    is_user_status_notification_enabled,
    set_user_status_notification_enabled,
    create_support_ticket,
    get_support_tickets,
    get_support_ticket,
    close_support_ticket,
    delete_old_closed_tickets,
    set_admin_new_order_template,
    set_notify_chat_id,
    set_payment_enabled,
    set_payment_setting,
    set_cryptobot_token,
    set_low_stock_threshold,
    set_start_command_description,
    set_user_status_template,
    business_hours_hint_html,
    get_business_hours_bounds,
    is_business_hours_restriction_enabled,
    is_within_business_hours,
    set_business_hours_enabled,
    set_business_hours_time,
    get_referral_bonus_amounts,
    is_referral_program_enabled,
    set_referral_program_enabled,
    set_referral_bonus_inviter,
    set_referral_bonus_referee,
)
from utils.db_api.sqlite import get_all_categoriesx
from utils.db_api.sqlite import path_to_db
from utils.bot_restart import cancel_restart_request, mark_restart_requested
from utils.ui_sections import ui_panel, ui_screen

router = Router(name="user_menu")
# Compatibility export for legacy imports expecting `dp` symbol.
dp = router


def _is_admin(user_id: int) -> bool:
    return is_admin_user(user_id)


def _settings_access(user_id: int) -> bool:
    if not _is_admin(user_id):
        return False
    return is_privileged_admin(user_id) or staff_has_perm(user_id, "settings")


def _support_tickets_access(user_id: int) -> bool:
    if not _is_admin(user_id):
        return False
    return is_privileged_admin(user_id) or staff_has_perm(user_id, "support")


def _get_admin_menu_kb(viewer_id: int) -> InlineKeyboardMarkup:
    if is_privileged_admin(viewer_id):
        return admin_menu_inline_kb(full_access=True)
    p = get_effective_staff_permissions(viewer_id)
    show_shop = any(p.get(k) for k in ("catalog", "payments", "support", "team", "io"))
    return admin_menu_inline_kb(
        full_access=False,
        show_shop=show_shop,
        show_insights=bool(p.get("insights")),
        show_settings=bool(p.get("settings")),
    )


def _get_admin_settings_kb(viewer_id: int) -> InlineKeyboardMarkup:
    return admin_settings_inline_kb(
        cod_enabled=is_payment_enabled("cod"),
        card_enabled=is_payment_enabled("card"),
        applepay_enabled=is_payment_enabled("applepay"),
        googlepay_enabled=is_payment_enabled("googlepay"),
        client_status_notif=is_user_status_notification_enabled(),
        maintenance_enabled=is_maintenance(),
        show_staff_permissions=is_owner_user(viewer_id),
    )


def _get_admin_settings_notif_kb() -> InlineKeyboardMarkup:
    return admin_settings_notifications_inline_kb(
        client_status_notif=is_user_status_notification_enabled(),
    )


def _get_admin_settings_payments_kb(viewer_id: int) -> InlineKeyboardMarkup:
    return admin_settings_payments_inline_kb(
        cod_enabled=is_payment_enabled("cod"),
        card_enabled=is_payment_enabled("card"),
        applepay_enabled=is_payment_enabled("applepay"),
        googlepay_enabled=is_payment_enabled("googlepay"),
        crypto_enabled=is_payment_enabled("crypto"),
        can_manage_crypto_token=is_owner_user(viewer_id),
    )


def _get_admin_settings_service_kb(viewer_id: int) -> InlineKeyboardMarkup:
    owner = is_owner_user(viewer_id)
    return admin_settings_service_inline_kb(can_update_repo=owner, can_manage_database=owner)


def _service_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅ К сервису", callback_data="admin:settings:service")]]
    )


def _admin_referral_text() -> str:
    en = is_referral_program_enabled()
    inv, ref = get_referral_bonus_amounts()
    st = "🟢 включена" if en else "🔴 выключена"
    return ui_panel(
        emoji="🤝",
        title="Пригласи друга",
        intro="Бонусы начисляются после первого оформленного заказа приглашённого пользователя.",
        body_lines=[
            f"📌 <b>Программа:</b> {st}",
            f"   ⤷ пригласившему: <b>{inv} грн</b>",
            f"   ⤷ новичку: <b>{ref} грн</b>",
        ],
    )


def _admin_business_hours_text() -> str:
    en = is_business_hours_restriction_enabled()
    hs, he = get_business_hours_bounds()
    st = "🟢 включено" if en else "🔴 выключено"
    return ui_panel(
        emoji="🕐",
        title="Время работы",
        intro="Эти часы действуют для приёма обращений в поддержку и для выбора доставки по городу при оформлении заказа.",
        body_lines=[
            f"📌 <b>Ограничение:</b> {st}",
            f"   ⤷ интервал: <b>{hs}</b> — <b>{he}</b>",
            "   ⤷ ориентир: часы сервера, на котором запущен бот",
            "",
            "🧭 <i>Ночная смена: задайте начало позже конца (например 22:00 и 06:00).</i>",
        ],
    )


def _admin_settings_text() -> str:
    chat_id = get_notify_chat_id() or "не задан"
    st = "✅ включены" if is_user_status_notification_enabled() else "❌ выключены"
    maint = "🛠 <b>включены</b> (клиенты не в магазин)" if is_maintenance() else "✅ выключены"
    ref_on = is_referral_program_enabled()
    r_inv, r_new = get_referral_bonus_amounts()
    ref_st = f"🟢 {r_inv}/{r_new} грн" if ref_on else "🔴 выкл"
    start_cmd = get_start_command_description()
    return ui_panel(
        emoji="⚙️",
        title="Настройки",
        intro="Витрина, уведомления и служебные инструменты — всё, что не требует ежедневного редактирования каталога.",
        body_lines=[
            "📌 <b>Сейчас в системе</b>",
            f"   ⤷ 🛠 техработы магазина: {maint}",
            f"   ⤷ 📬 авто-статус клиенту: <b>{st}</b>",
            f"   ⤷ ⌨️ меню /start: <b>{start_cmd}</b>",
            f"   ⤷ 📢 лог-чат заказов: <code>{chat_id}</code>",
            f"   ⤷ 🤝 рефералка: <b>{ref_st}</b>",
            "",
            "🧭 <b>Разделы ниже</b>",
            "   ⤷ 🎨 <b>Оформление</b> · приветствие и главное меню",
            "   ⤷ 🔔 <b>Шаблоны</b> · тексты уведомлений и каналы",
            "   ⤷ 🕐 <b>Время работы</b> · поддержка и доставка по городу",
            "   ⤷ 🤝 <b>Пригласи друга</b> · вкл/выкл и суммы бонусов",
            "   ⤷ 🛠 <b>Техработы</b> · витрина недоступна клиентам (админы ходят как обычно)",
            "   ⤷ 🗂 <b>Сервис</b> · резервная копия базы",
            "",
            "📝 <b>Плейсхолдеры</b> <i>(для шаблонов заказов)</i>",
            "<code>{order_id}</code> <code>{status}</code> <code>{name}</code>",
            "<code>{phone}</code> <code>{total}</code> <code>{delivery}</code> <code>{payment}</code>",
        ],
    )


def _admin_settings_notifications_text() -> str:
    chat_id = get_notify_chat_id() or "не задан"
    st = "✅ включены" if is_user_status_notification_enabled() else "❌ выключены"
    start_cmd = get_start_command_description()
    return ui_panel(
        emoji="🔔",
        title="Шаблоны и уведомления",
        intro="Тексты для админов и клиентов, плюс куда дублировать заказы.",
        body_lines=[
            "📌 <b>Текущие значения</b>",
            f"   ⤷ 📬 авто-статус клиенту: <b>{st}</b>",
            f"   ⤷ 📢 лог-чат: <code>{chat_id}</code>",
            f"   ⤷ ⌨️ описание /start: <b>{start_cmd}</b>",
            "",
            "🧭 <b>Кнопки этого экрана</b>",
            "   ⤷ 🔔 шаблон «новый заказ» для админов",
            "   ⤷ 📦 шаблон «статус» для покупателя",
            "   ⤷ ✏️ текст пункта /start в меню бота",
            "   ⤷ 📬 мастер-переключатель авто-статусов",
            "   ⤷ 📢 привязка лог-чата по chat_id",
            "",
            "📝 <b>Плейсхолдеры</b>",
            "<code>{order_id}</code> <code>{status}</code> <code>{name}</code>",
            "<code>{phone}</code> <code>{total}</code> <code>{delivery}</code> <code>{payment}</code>",
        ],
    )


def _admin_settings_payments_text() -> str:
    cod = "✅ включен" if is_payment_enabled("cod") else "❌ выключен"
    card = "✅ настроена" if get_payment_info("card") else "➖ не настроена"
    apple = "✅ настроен" if get_payment_info("applepay") else "➖ не настроен"
    google = "✅ настроен" if get_payment_info("googlepay") else "➖ не настроен"
    crypto = "✅ включён" if is_payment_enabled("crypto") else ("🔴 выключен" if get_cryptobot_token() else "➖ не задан токен")
    return ui_panel(
        emoji="💳",
        title="Настройки оплаты",
        intro="Включите методы и заполните реквизиты — клиент увидит их на шаге оплаты.",
        body_lines=[
            "📌 <b>Состояние методов</b>",
            f"   ⤷ 🚚 наложенный платёж: <b>{cod}</b>",
            f"   ⤷ 💳 банковская карта: <b>{card}</b>",
            f"   ⤷ 🍏 Apple Pay: <b>{apple}</b>",
            f"   ⤷ 🤖 Google Pay: <b>{google}</b>",
            f"   ⤷ 🪙 CryptoBot: <b>{crypto}</b>",
            "",
            "💡 <i>Строки с индикатором 🟢/🔴 ниже переключают доступность у клиента.</i>",
        ],
    )


async def _safe_edit(message: Message, text: str, reply_markup=None, disable_web_page_preview: bool = False) -> None:
    try:
        if message.photo:
            await message.edit_caption(caption=text, reply_markup=reply_markup)
        else:
            await message.edit_text(text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
    except TelegramBadRequest as error:
        err = str(error).lower()
        if "message is not modified" in err:
            return
        if "there is no text in the message to edit" in err or "there is no caption in the message to edit" in err:
            await message.answer(text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
            return
        raise


@router.message(CommandStart())
@router.message(F.text == "⬅ На главную")
async def open_main_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    parts = (message.text or "").split(maxsplit=1)
    start_arg = parts[1].strip() if len(parts) > 1 else ""
    display_name = message.from_user.first_name or message.from_user.username or str(message.from_user.id)
    ensure_user(message.from_user.id, display_name)
    apply_referral_from_start_payload(message.from_user.id, start_arg)
    if is_referral_program_enabled():
        get_or_create_referral_code(message.from_user.id)
    welcome_text, welcome_photo = get_welcome_message()
    if is_maintenance() and not _is_admin(message.from_user.id):
        welcome_text = f"{welcome_text}\n\n<b>🛠 Магазин временно на техработах</b>"

    kb = main_menu_inline_kb(is_admin=_is_admin(message.from_user.id))
    banner_local = get_default_menu_banner_path()
    if welcome_photo:
        await message.answer_photo(
            welcome_photo,
            caption=welcome_text,
            reply_markup=kb,
            parse_mode="HTML",
        )
    elif banner_local:
        await message.answer_photo(
            FSInputFile(banner_local),
            caption=welcome_text,
            reply_markup=kb,
            parse_mode="HTML",
        )
    else:
        await message.answer(welcome_text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "menu:main")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if is_referral_program_enabled():
        get_or_create_referral_code(callback.from_user.id)
    main_menu_text, main_menu_photo = get_main_menu_message()
    kb = main_menu_inline_kb(is_admin=_is_admin(callback.from_user.id))
    banner_local = get_default_menu_banner_path()

    if main_menu_photo:
        await callback.message.delete()
        await callback.bot.send_photo(
            chat_id=callback.from_user.id,
            photo=main_menu_photo,
            caption=main_menu_text,
            reply_markup=kb,
            parse_mode="HTML",
        )
    elif banner_local:
        await callback.message.delete()
        await callback.bot.send_photo(
            chat_id=callback.from_user.id,
            photo=FSInputFile(banner_local),
            caption=main_menu_text,
            reply_markup=kb,
            parse_mode="HTML",
        )
    else:
        await _safe_edit(callback.message, main_menu_text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "menu:accounts")
async def callback_accounts(callback: CallbackQuery) -> None:
    await _safe_edit(
        callback.message,
        ui_panel(
            emoji="🛍",
            title="Каталог",
            intro="Полный список категорий и поиск по витрине — в разделе «Каталог» главного меню.",
            body_lines=["🧭 <i>Нажмите «Каталог» на клавиатуре ниже, чтобы продолжить.</i>"],
        ),
        reply_markup=main_menu_inline_kb(is_admin=_is_admin(callback.from_user.id)),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("category:"))
async def callback_category_selected(callback: CallbackQuery) -> None:
    _, raw_category_id = callback.data.split(":", maxsplit=1)
    category_id = int(raw_category_id)

    categories = get_all_categoriesx()
    category_name = next((row[1] for row in categories if row[0] == category_id), None)
    if category_name is None:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    await _safe_edit(
        callback.message,
        ui_panel(
            emoji="📂",
            title="Категория",
            intro=f"Вы выбрали раздел «{category_name}».",
            body_lines=[
                "📋 <i>Список товаров этой категории открывается из основного каталога магазина.</i>",
                "🗂 <i>Нажмите «Каталог» ниже и выберите ту же категорию в боте магазина.</i>",
            ],
        ),
        reply_markup=main_menu_inline_kb(is_admin=_is_admin(callback.from_user.id)),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:profile")
async def callback_profile(callback: CallbackQuery) -> None:
    ensure_user(
        callback.from_user.id,
        callback.from_user.first_name or callback.from_user.username or str(callback.from_user.id),
    )
    profile = get_shop_user_profile(callback.from_user.id)
    ref_enabled = is_referral_program_enabled()
    ref_code = get_or_create_referral_code(callback.from_user.id) if ref_enabled else ""
    uname = (bot_username or "").strip().lstrip("@")
    ref_link = f"https://t.me/{uname}?start=ref_{ref_code}" if ref_code and uname else ""
    username = callback.from_user.first_name or callback.from_user.username or "не указан"
    reg_date = profile.get("created_at") or "—"
    bonus = profile.get("bonus", 0)
    bonus_block = (
        [f"   ⤷ 🎁 бонусный счёт: <b>{bonus} грн</b>"]
        if bonus > 0
        else ["   ⤷ 🎁 бонусный счёт: <i>пока нет начислений</i>"]
    )
    ref_lines: list[str] = []
    if ref_enabled and ref_code:
        ref_lines = [
            "",
            "🤝 <b>Пригласи друга</b>",
            f"   ⤷ код: <code>{ref_code}</code>",
        ]
        if ref_link:
            ref_lines.append(f"   ⤷ ссылка: <code>{ref_link}</code>")
        ref_lines.append("   ⤷ <i>после первого заказа приглашённого — бонусы вам обоим</i>")
    profile_text = ui_panel(
        emoji="👤",
        title="Личный кабинет",
        intro="Краткая информация об аккаунте.",
        body_lines=[
            "📌 <b>Ваш профиль</b>",
            f"   ⤷ 🆔 Telegram ID: <code>{callback.from_user.id}</code>",
            f"   ⤷ 🔖 имя в Telegram: <b>{username}</b>",
            *bonus_block,
            f"   ⤷ 📅 регистрация: <b>{reg_date}</b>",
            *ref_lines,
        ],
    )

    await _safe_edit(
        callback.message,
        profile_text,
        reply_markup=profile_actions_inline_kb,
    )
    await callback.answer()


@router.callback_query(F.data == "menu:faq")
async def callback_faq(callback: CallbackQuery) -> None:
    send_msg = bot_description
    if "{username}" in send_msg:
        send_msg = send_msg.replace("{username}", f"<b>{callback.from_user.username}</b>")
    if "{user_id}" in send_msg:
        send_msg = send_msg.replace("{user_id}", f"<b>{callback.from_user.id}</b>")
    if "{firstname}" in send_msg:
        send_msg = send_msg.replace("{firstname}", f"<b>{callback.from_user.first_name}</b>")

    await _safe_edit(
        callback.message,
        send_msg,
        disable_web_page_preview=True,
        reply_markup=main_menu_inline_kb(is_admin=_is_admin(callback.from_user.id)),
    )
    await callback.answer()


@router.callback_query(F.data == "profile:purchases")
async def callback_profile_purchases(callback: CallbackQuery) -> None:
    await callback.answer("Используйте кнопку 'Мои заказы'", show_alert=True)


@router.callback_query(F.data == "profile:back")
async def callback_profile_back(callback: CallbackQuery) -> None:
    main_menu_text, main_menu_photo = get_main_menu_message()
    kb = main_menu_inline_kb(is_admin=_is_admin(callback.from_user.id))
    banner_local = get_default_menu_banner_path()

    if main_menu_photo:
        await callback.message.delete()
        await callback.bot.send_photo(
            chat_id=callback.from_user.id,
            photo=main_menu_photo,
            caption=main_menu_text,
            reply_markup=kb,
            parse_mode="HTML",
        )
    elif banner_local:
        await callback.message.delete()
        await callback.bot.send_photo(
            chat_id=callback.from_user.id,
            photo=FSInputFile(banner_local),
            caption=main_menu_text,
            reply_markup=kb,
            parse_mode="HTML",
        )
    else:
        await _safe_edit(callback.message, main_menu_text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "menu:support")
async def callback_support_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    closed = ""
    if is_business_hours_restriction_enabled() and not is_within_business_hours():
        closed = (
            "\n\n⚠️ <b>Сейчас нерабочее время</b>\n"
            f"<i>{business_hours_hint_html()}</i>\n"
            "<i>Новые обращения временно не принимаются.</i>"
        )
    await _safe_edit(
        callback.message,
        "<b>🛟 Поддержка</b>\n"
        "──────────────\n"
        "<i>Вопрос по заказу, оплате или работе бота? Напишите нам, и мы ответим в ближайшее время.</i>"
        f"{closed}",
        reply_markup=support_menu_inline_kb,
    )
    await callback.answer()


@router.callback_query(F.data == "support:start")
async def callback_support_start(callback: CallbackQuery, state: FSMContext) -> None:
    if is_business_hours_restriction_enabled() and not is_within_business_hours():
        await callback.answer(
            f"Сейчас нерабочее время. {get_business_hours_bounds()[0]}–{get_business_hours_bounds()[1]} (время сервера бота).",
            show_alert=True,
        )
        return
    await state.set_state(SupportDialog.user_message)
    await _safe_edit(
        callback.message,
        "<b>✍ Обращение</b>\n"
        "──────────────\n"
        "<i>Опишите вопрос сообщением. При необходимости можно приложить <b>фото</b> или <b>файл</b>.</i>",
        reply_markup=support_back_inline_kb,
    )
    await callback.answer()


@router.message(SupportDialog.user_message)
async def support_user_message_send(message: Message, state: FSMContext) -> None:
    if is_business_hours_restriction_enabled() and not is_within_business_hours():
        await state.clear()
        hs, he = get_business_hours_bounds()
        await message.answer(
            "<b>🕐 Нерабочее время</b>\n──────────────\n"
            f"<i>Приём обращений с {hs} до {he} (время сервера бота).</i>",
            reply_markup=support_menu_inline_kb,
        )
        return

    text_body = (message.text or message.caption or "").strip()
    has_photo = bool(message.photo)
    has_document = bool(message.document)

    if not text_body and not has_photo and not has_document:
        await message.answer(
            "<b>⚠ Нужно содержимое</b>\n\n"
            "<i>Отправьте текст, фото или документ.</i>",
            reply_markup=support_back_inline_kb,
        )
        return

    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""

    media_file_id = message.photo[-1].file_id if has_photo else (message.document.file_id if has_document else "")
    media_type = "photo" if has_photo else ("document" if has_document else "")

    # Save ticket to DB (for media-only messages store a short marker)
    ticket_text = text_body or ("[фото]" if has_photo else "[файл]")
    ticket_id = create_support_ticket(
        user_id,
        username,
        first_name,
        ticket_text,
        media_file_id=media_file_id,
        media_type=media_type,
    )

    support_ids = get_support_admin_ids()
    if not support_ids:
        support_ids = get_admin_ids()

    payload_header = (
        f"<b>🛟 Новое обращение #{ticket_id}</b>\n"
        f"👤 Клиент: <code>{user_id}</code>\n"
        f"🔖 Username: <b>{username or '-'}</b>\n"
        f"🙍 Имя: <b>{first_name or '-'}</b>\n\n"
        f"💬 Сообщение:\n"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✍️ Ответить клиенту", callback_data=f"support:reply:{ticket_id}")]]
    )
    delivered = 0
    for admin_id in support_ids:
        try:
            if has_photo:
                await message.bot.send_photo(
                    int(admin_id),
                    photo=message.photo[-1].file_id,
                    caption=payload_header + (text_body or ""),
                    reply_markup=kb,
                )
            elif has_document:
                await message.bot.send_document(
                    int(admin_id),
                    document=message.document.file_id,
                    caption=payload_header + (text_body or ""),
                    reply_markup=kb,
                )
            else:
                await message.bot.send_message(int(admin_id), payload_header + text_body, reply_markup=kb)
            delivered += 1
        except Exception:
            pass

    await state.clear()
    if delivered == 0:
        await message.answer(
            "<b>✅ Обращение принято</b>\n"
            "──────────────\n"
            "Сейчас специалисты недоступны, но мы свяжемся с вами. 🕐\n\n"
            "<i>Служба поддержки</i>",
            reply_markup=support_menu_inline_kb,
        )
        return
    await message.answer(
        "<b>✅ Обращение принято</b>\n"
        "──────────────\n"
        "Специалист ответит в ближайшее время. 🕐\n\n"
        "<i>Служба поддержки</i>",
        reply_markup=support_menu_inline_kb,
    )


@router.callback_query(F.data.startswith("support:reply:"))
async def support_admin_reply_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _support_tickets_access(callback.from_user.id):
        await callback.answer("Нет доступа к обращениям поддержки", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[-1])
    ticket = get_support_ticket(ticket_id)
    if not ticket:
        await callback.answer("Обращение не найдено", show_alert=True)
        return

    target_user_id = ticket["user_id"]
    first_name = ticket["first_name"] or ticket["username"] or str(target_user_id)
    await state.set_state(SupportDialog.admin_reply)
    await state.update_data(support_target_user_id=target_user_id, support_ticket_id=ticket_id)
    await callback.message.answer(
        f"✍️ Введите ответ для клиента <b>{first_name}</b>\n"
        f"📋 Обращение #{ticket_id}\n\n"
        "Можно прикрепить фото или файл 📎",
        reply_markup=admin_reply_cancel_kb,
    )
    await callback.answer()


@router.message(SupportDialog.admin_reply)
async def support_admin_reply_send(message: Message, state: FSMContext) -> None:
    if not _support_tickets_access(message.from_user.id):
        await state.clear()
        await message.answer(
            "<b>🚫 Нет доступа</b>\n\n<i>Нет права на ответы в поддержке.</i>",
            reply_markup=admin_reply_cancel_kb,
        )
        return

    text_body = (message.text or message.caption or "").strip()
    has_photo = bool(message.photo)
    has_document = bool(message.document)

    if not text_body and not has_photo and not has_document:
        await message.answer(
            "<b>⚠ Пустой ответ</b>\n\n<i>Введите текст или приложите фото / файл.</i>",
            reply_markup=admin_reply_cancel_kb,
        )
        return

    data = await state.get_data()
    target_user_id = int(data.get("support_target_user_id", 0) or 0)
    ticket_id_done = int(data.get("support_ticket_id", 0) or 0)
    if not target_user_id:
        await state.clear()
        await message.answer(
            "<b>❌ Ошибка</b>\n\n<i>Не удалось определить клиента. Начните ответ из списка обращений.</i>",
            reply_markup=admin_reply_cancel_kb,
        )
        return

    reply_header = "🛟 <b>Ответ службы поддержки</b>\n\n"

    try:
        if has_photo:
            await message.bot.send_photo(
                target_user_id,
                photo=message.photo[-1].file_id,
                caption=reply_header + (text_body or ""),
                reply_markup=support_menu_inline_kb,
            )
        elif has_document:
            await message.bot.send_document(
                target_user_id,
                document=message.document.file_id,
                caption=reply_header + (text_body or ""),
                reply_markup=support_menu_inline_kb,
            )
        else:
            await message.bot.send_message(
                target_user_id,
                reply_header + text_body,
                reply_markup=support_menu_inline_kb,
            )
    except Exception:
        await state.clear()
        await message.answer(
            "<b>❌ Не отправлено</b>\n\n"
            "<i>Клиент не получил сообщение (не писал боту или заблокировал).</i>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📋 К обращениям", callback_data="admin:support_tickets")],
                    [InlineKeyboardButton(text="⬅ Управление магазином", callback_data="admin:shop")],
                ]
            ),
        )
        return

    await state.clear()
    await message.answer(
        "<b>✅ Ответ доставлен клиенту</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📋 К обращению",
                        callback_data=f"admin:ticket:{ticket_id_done}" if ticket_id_done else "admin:support_tickets",
                    )
                ],
                [InlineKeyboardButton(text="⬅ Все обращения", callback_data="admin:support_tickets")],
                [InlineKeyboardButton(text="⬅ Управление магазином", callback_data="admin:shop")],
            ]
        ),
    )


@router.callback_query(F.data == "admin:support_tickets")
async def callback_admin_support_tickets(callback: CallbackQuery) -> None:
    if not _support_tickets_access(callback.from_user.id):
        await callback.answer("Нет доступа к обращениям поддержки", show_alert=True)
        return

    tickets = get_support_tickets(status="active")
    active = len(tickets)
    closed = len(get_support_tickets(status="closed"))

    if not tickets:
        text = (
            "🛟 <b>Обращения в поддержку</b>\n\n"
            f"🟢 Активных: <b>{active}</b>   🔴 Закрытых: <b>{closed}</b>\n\n"
            "😊 Активных обращений нет — всё спокойно!"
        )
    else:
        text = (
            "🛟 <b>Обращения в поддержку</b>\n\n"
            f"🟢 Активных: <b>{active}</b>   🔴 Закрытых: <b>{closed}</b>\n\n"
            "👇 Выберите обращение для просмотра:"
        )

    await _safe_edit(callback.message, text, reply_markup=support_tickets_list_kb(tickets, show_closed=False))
    await callback.answer()


@router.callback_query(F.data == "admin:support_tickets:closed")
async def callback_admin_support_tickets_closed(callback: CallbackQuery) -> None:
    if not _support_tickets_access(callback.from_user.id):
        await callback.answer("Нет доступа к обращениям поддержки", show_alert=True)
        return

    tickets = get_support_tickets(status="closed")
    active = len(get_support_tickets(status="active"))
    closed = len(tickets)

    if not tickets:
        text = (
            "📁 <b>Завершённые обращения</b>\n\n"
            f"🟢 Активных: <b>{active}</b>   🔴 Закрытых: <b>{closed}</b>\n\n"
            "Закрытых обращений пока нет."
        )
    else:
        text = (
            "📁 <b>Завершённые обращения</b>\n\n"
            f"🟢 Активных: <b>{active}</b>   🔴 Закрытых: <b>{closed}</b>\n\n"
            "👇 Выберите обращение для просмотра:"
        )

    await _safe_edit(callback.message, text, reply_markup=support_tickets_list_kb(tickets, show_closed=True))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:ticket:close:"))
async def callback_admin_ticket_close(callback: CallbackQuery) -> None:
    if not _support_tickets_access(callback.from_user.id):
        await callback.answer("Нет доступа к обращениям поддержки", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[-1])
    close_support_ticket(ticket_id)
    await callback.answer("✅ Обращение закрыто")

    ticket = get_support_ticket(ticket_id)
    if ticket:
        name = ticket["first_name"] or ticket["username"] or str(ticket["user_id"])
        status_text = "🔴 Закрыто"
        text = (
            f"<b>🛟 Обращение #{ticket_id}</b>\n"
            f"👤 Клиент: <b>{name}</b> (<code>{ticket['user_id']}</code>)\n"
            f"📅 Дата: <b>{ticket['created_at']}</b>\n"
            f"📌 Статус: <b>{status_text}</b>\n\n"
            f"💬 Сообщение:\n{ticket['message']}"
        )
        await _safe_edit(callback.message, text, reply_markup=support_ticket_view_kb(ticket_id, "closed"))


@router.callback_query(F.data.startswith("admin:ticket:"))
async def callback_admin_ticket_view(callback: CallbackQuery) -> None:
    if not _support_tickets_access(callback.from_user.id):
        await callback.answer("Нет доступа к обращениям поддержки", show_alert=True)
        return

    # Skip "admin:ticket:close:" — handled above
    parts = callback.data.split(":")
    if len(parts) > 3:
        return

    ticket_id = int(parts[-1])
    ticket = get_support_ticket(ticket_id)
    if not ticket:
        await callback.answer("Обращение не найдено", show_alert=True)
        return

    name = ticket["first_name"] or ticket["username"] or str(ticket["user_id"])
    status_text = "🟢 Активно" if ticket["status"] == "active" else "🔴 Закрыто"
    text = (
        f"<b>🛟 Обращение #{ticket_id}</b>\n"
        f"👤 Клиент: <b>{name}</b> (<code>{ticket['user_id']}</code>)\n"
        f"📅 Дата: <b>{ticket['created_at']}</b>\n"
        f"📌 Статус: <b>{status_text}</b>\n\n"
        f"💬 Сообщение:\n{ticket['message']}"
    )

    media_file_id = str(ticket.get("media_file_id", "") or "").strip()
    media_type = str(ticket.get("media_type", "") or "").strip().lower()
    if media_file_id and media_type in {"photo", "document"}:
        try:
            if media_type == "photo":
                ticket_back = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅ К обращению", callback_data=f"admin:ticket:{ticket_id}")],
                    ]
                )
                await callback.message.answer_photo(
                    media_file_id,
                    caption=f"<b>🧾 Вложение</b> к обращению <code>#{ticket_id}</code>",
                    reply_markup=ticket_back,
                )
            else:
                ticket_back = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅ К обращению", callback_data=f"admin:ticket:{ticket_id}")],
                    ]
                )
                await callback.message.answer_document(
                    media_file_id,
                    caption=f"<b>🧾 Вложение</b> к обращению <code>#{ticket_id}</code>",
                    reply_markup=ticket_back,
                )
        except Exception:
            pass

    await _safe_edit(callback.message, text, reply_markup=support_ticket_view_kb(ticket_id, ticket["status"]))
    await callback.answer()


@router.callback_query(F.data == "menu:admin")
async def callback_admin_menu(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await _safe_edit(
        callback.message,
        ui_screen(
            emoji="🔧",
            title="Панель администратора",
            intro="Центр управления магазином: витрина, цифры и глобальные настройки.",
            groups=[
                ("🛒", "Управление магазином", "Каталог, заказы, доставка, промо и команда"),
                ("📊", "Информация и статистика", "О боте, сводки и список клиентов"),
                ("⚙️", "Настройки", "Оформление, шаблоны, оплата и бэкап"),
            ],
        ),
        reply_markup=_get_admin_menu_kb(callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:bot_info")
async def callback_admin_bot_info(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    stats = get_shop_stats()
    text = ui_panel(
        emoji="📰",
        title="О боте",
        intro="Сводная карточка экземпляра бота и ключевые показатели магазина.",
        body_lines=[
            "🖥 <b>Система</b>",
            f"   ⤷ 🤖 ID бота: <code>{callback.bot.id}</code>",
            f"   ⤷ 👤 ваш Telegram ID: <code>{callback.from_user.id}</code>",
            "",
            "🛍 <b>Магазин</b>",
            f"   ⤷ 👥 клиентов: <b>{stats['customers']}</b>",
            f"   ⤷ ⚙️ администраторов: <b>{stats['admins']}</b>",
            "",
            "📚 <b>Каталог</b>",
            f"   ⤷ 📁 категорий: <b>{stats['categories']}</b>",
            f"   ⤷ 📦 товаров: <b>{stats['products']}</b>",
            "",
            "📋 <b>Заказы</b>",
            f"   ⤷ 🆕 новых: <b>{stats['orders_new']}</b>",
            f"   ⤷ ⚡ в работе: <b>{stats['orders_inwork']}</b>",
            f"   ⤷ 📂 в архиве: <b>{stats['orders_archive']}</b>",
            f"   ⤷ 📊 всего: <b>{stats['orders']}</b>",
            "",
            f"💰 <b>Выручка (всего):</b> {stats['revenue']:,} грн",
        ],
    )

    await _safe_edit(
        callback.message,
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="admin:section:insights")]]
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:settings")
async def callback_admin_settings(callback: CallbackQuery) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return

    await _safe_edit(
        callback.message,
        _admin_settings_text(),
        reply_markup=_get_admin_settings_kb(callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:settings:staff_perms")
async def callback_admin_settings_staff_perms(callback: CallbackQuery) -> None:
    if not is_owner_user(callback.from_user.id):
        await callback.answer("Только владелец может менять права персонала", show_alert=True)
        return

    await _safe_edit(
        callback.message,
        ui_panel(
            emoji="👥",
            title="Права персонала",
            intro="Выберите роль, затем сотрудника — для каждого можно включить или отключить пункты меню (🟢 да · 🔴 нет).",
            body_lines=[
                "📋 <b>Менеджер</b> — доступ к операционным разделам по выбранным правам.",
                "🛟 <b>Техподдержка</b> — обычно только тикеты; остальное при необходимости включите вручную.",
            ],
        ),
        reply_markup=admin_staff_role_pick_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:staff_perm:list:"))
async def callback_admin_staff_perm_list(callback: CallbackQuery) -> None:
    if not is_owner_user(callback.from_user.id):
        await callback.answer("Только владелец может менять права персонала", show_alert=True)
        return

    role_kind = callback.data.split(":")[-1]
    if role_kind not in ("manager", "support"):
        await callback.answer("Некорректная роль", show_alert=True)
        return

    users = list_staff_by_roles(roles=(role_kind,))
    label = "менеджеров" if role_kind == "manager" else "техподдержки"
    if not users:
        text = ui_panel(
            emoji="👥",
            title="Права персонала",
            intro=f"Список {label} пуст.",
            body_lines=["Добавьте сотрудников через карточку клиента: «Добавить в штат»."],
        )
    else:
        text = ui_panel(
            emoji="👥",
            title="Права персонала",
            intro=f"Выберите сотрудника ({label}):",
            body_lines=[],
        )

    await _safe_edit(callback.message, text, reply_markup=admin_staff_users_kb(users, role_kind=role_kind))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:staff_perm:edit:"))
async def callback_admin_staff_perm_edit(callback: CallbackQuery) -> None:
    if not is_owner_user(callback.from_user.id):
        await callback.answer("Только владелец может менять права персонала", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 5:
        await callback.answer("Ошибка данных", show_alert=True)
        return

    uid = int(parts[3])
    role_kind = parts[4]
    prof = get_shop_user_profile(uid)
    if (prof.get("role") or "").strip() != role_kind:
        await callback.answer("Роль изменилась — откройте список снова", show_alert=True)
        return

    eff = get_effective_staff_permissions(uid)
    title = "менеджера" if role_kind == "manager" else "техподдержки"
    nm = (prof.get("name") or "").strip() or str(uid)
    await _safe_edit(
        callback.message,
        ui_panel(
            emoji="👤",
            title=f"Права · {title}",
            intro=f"<b>{html.escape(nm)}</b> <code>{uid}</code>",
            body_lines=["Нажмите на строку, чтобы переключить доступ."],
        ),
        reply_markup=staff_permissions_editor_kb(uid, eff, role_kind=role_kind),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:staff_perm:toggle:"))
async def callback_admin_staff_perm_toggle(callback: CallbackQuery) -> None:
    if not is_owner_user(callback.from_user.id):
        await callback.answer("Только владелец может менять права персонала", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 5:
        await callback.answer("Ошибка данных", show_alert=True)
        return

    uid = int(parts[3])
    perm_key = parts[4]
    new_val = toggle_staff_perm_for_user(uid, perm_key)
    if new_val is None:
        await callback.answer("Не удалось переключить право", show_alert=True)
        return

    prof = get_shop_user_profile(uid)
    role_kind = (prof.get("role") or "").strip()
    eff = get_effective_staff_permissions(uid)
    title = "менеджера" if role_kind == "manager" else "техподдержки"
    nm = (prof.get("name") or "").strip() or str(uid)
    await _safe_edit(
        callback.message,
        ui_panel(
            emoji="👤",
            title=f"Права · {title}",
            intro=f"<b>{html.escape(nm)}</b> <code>{uid}</code>",
            body_lines=["Нажмите на строку, чтобы переключить доступ."],
        ),
        reply_markup=staff_permissions_editor_kb(uid, eff, role_kind=role_kind),
    )
    await callback.answer("Сохранено")


@router.callback_query(F.data == "admin:maintenance:toggle")
async def callback_admin_maintenance_toggle(callback: CallbackQuery) -> None:
    if not is_privileged_admin(callback.from_user.id):
        await callback.answer("Только владелец или админ может переключать техработы", show_alert=True)
        return
    toggle_maintenance()
    on = is_maintenance()
    await _safe_edit(
        callback.message,
        _admin_settings_text(),
        reply_markup=_get_admin_settings_kb(callback.from_user.id),
    )
    await callback.answer("🛠 Техработы ВКЛ — клиенты не попадут в магазин" if on else "✅ Техработы ВЫКЛ — витрина снова для всех", show_alert=True)


@router.callback_query(F.data == "admin:settings:notif")
async def callback_admin_settings_notif(callback: CallbackQuery) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return

    await _safe_edit(
        callback.message,
        _admin_settings_notifications_text(),
        reply_markup=_get_admin_settings_notif_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:settings:payments")
async def callback_admin_settings_payments(callback: CallbackQuery) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return

    await _safe_edit(
        callback.message,
        _admin_settings_payments_text(),
        reply_markup=_get_admin_settings_payments_kb(callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:settings:service")
async def callback_admin_settings_service(callback: CallbackQuery) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return

    await _safe_edit(
        callback.message,
        ui_screen(
            emoji="🗂",
            title="Сервис",
            intro="Инструменты для обслуживания данных — используйте перед крупными изменениями.",
            groups=[
                ("💾", "Бэкап базы", "Скачать копию SQLite одним файлом"),
                ("🗑 · 📤", "Удаление и загрузка БД", "Только владелец: сброс с автобэкапом или замена файла из Telegram"),
                ("🔄", "Обновить с Git", "Подтянуть изменения из репозитория (только владелец)"),
                ("♻️", "Перезапуск", "Новый процесс Python — нужен после обновления файлов (только владелец)"),
            ],
        ),
        reply_markup=_get_admin_settings_service_kb(callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:settings:business_hours")
async def callback_admin_settings_business_hours(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return
    await state.clear()
    await _safe_edit(
        callback.message,
        _admin_business_hours_text(),
        reply_markup=admin_business_hours_kb(enabled=is_business_hours_restriction_enabled()),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:bhours:toggle")
async def callback_admin_bhours_toggle(callback: CallbackQuery) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return
    set_business_hours_enabled(not is_business_hours_restriction_enabled())
    await _safe_edit(
        callback.message,
        _admin_business_hours_text(),
        reply_markup=admin_business_hours_kb(enabled=is_business_hours_restriction_enabled()),
    )
    await callback.answer("✅ Сохранено")


@router.callback_query(F.data == "admin:bhours:start")
async def callback_admin_bhours_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return
    await state.set_state(AdminBusinessHours.start_time)
    hs, _ = get_business_hours_bounds()
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅ Отмена", callback_data="admin:bhours:cancel")]]
    )
    await callback.message.answer(
        f"🕐 <b>Время начала приёма</b>\n\n"
        f"Сейчас: <code>{hs}</code>\n"
        "Отправьте новое значение в формате <b>ЧЧ:ММ</b> (например <code>09:00</code>).",
        reply_markup=cancel_kb,
    )
    await callback.answer()


@router.callback_query(F.data == "admin:bhours:end")
async def callback_admin_bhours_end(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return
    await state.set_state(AdminBusinessHours.end_time)
    _, he = get_business_hours_bounds()
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅ Отмена", callback_data="admin:bhours:cancel")]]
    )
    await callback.message.answer(
        f"🕙 <b>Время окончания приёма</b>\n\n"
        f"Сейчас: <code>{he}</code>\n"
        "Отправьте новое значение в формате <b>ЧЧ:ММ</b> (например <code>21:00</code>).",
        reply_markup=cancel_kb,
    )
    await callback.answer()


@router.callback_query(F.data == "admin:bhours:cancel")
async def callback_admin_bhours_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return
    await state.clear()
    await _safe_edit(
        callback.message,
        _admin_business_hours_text(),
        reply_markup=admin_business_hours_kb(enabled=is_business_hours_restriction_enabled()),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:settings:referral")
async def callback_admin_settings_referral(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return
    await state.clear()
    inv, ref = get_referral_bonus_amounts()
    await _safe_edit(
        callback.message,
        _admin_referral_text(),
        reply_markup=admin_referral_kb(enabled=is_referral_program_enabled(), inviter=inv, referee=ref),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:settings:stock_alerts")
async def callback_admin_settings_stock_alerts(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return
    await state.set_state(AdminStockAlerts.threshold)
    cur = get_low_stock_threshold()
    await callback.message.answer(
        "📦 <b>Уведомления по низкому остатку</b>\n\n"
        f"Текущий порог: <b>{cur}</b> шт\n\n"
        "Отправьте новое значение (целое число).\n"
        "Пример: <code>3</code>\n\n"
        "<i>0 — отключить уведомления.</i>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад · настройки", callback_data="admin:settings")]]
        ),
    )
    await callback.answer()


@router.message(AdminStockAlerts.threshold)
async def callback_admin_settings_stock_alerts_set(message: Message, state: FSMContext) -> None:
    if not _settings_access(message.from_user.id):
        await state.clear()
        return
    raw = (message.text or "").strip()
    try:
        v = int(raw)
    except ValueError:
        await message.answer(
            "<b>⚠ Нужно целое число</b>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад · настройки", callback_data="admin:settings")]]
            ),
        )
        return
    set_low_stock_threshold(v)
    await state.clear()
    await message.answer(
        f"✅ <b>Порог сохранён</b>\n<i>Теперь уведомления будут при остатке ≤ {get_low_stock_threshold()} шт.</i>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад · настройки", callback_data="admin:settings")]]
        ),
    )


@router.callback_query(F.data == "admin:referral:toggle")
async def callback_admin_referral_toggle(callback: CallbackQuery) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return
    set_referral_program_enabled(not is_referral_program_enabled())
    inv, ref = get_referral_bonus_amounts()
    await _safe_edit(
        callback.message,
        _admin_referral_text(),
        reply_markup=admin_referral_kb(enabled=is_referral_program_enabled(), inviter=inv, referee=ref),
    )
    await callback.answer("✅ Сохранено")


@router.callback_query(F.data == "admin:referral:inviter")
async def callback_admin_referral_inviter(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return
    await state.set_state(AdminReferral.inviter_bonus)
    inv, _ = get_referral_bonus_amounts()
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅ Отмена", callback_data="admin:referral:cancel")]]
    )
    await callback.message.answer(
        f"🎁 <b>Бонус пригласившему</b>\n\n"
        f"Сейчас: <b>{inv} грн</b>\n"
        "Отправьте целое число (грн), <code>0</code> — не начислять.",
        reply_markup=cancel_kb,
    )
    await callback.answer()


@router.callback_query(F.data == "admin:referral:referee")
async def callback_admin_referral_referee(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return
    await state.set_state(AdminReferral.referee_bonus)
    _, ref = get_referral_bonus_amounts()
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅ Отмена", callback_data="admin:referral:cancel")]]
    )
    await callback.message.answer(
        f"🎁 <b>Бонус новичку</b>\n\n"
        f"Сейчас: <b>{ref} грн</b>\n"
        "Отправьте целое число (грн), <code>0</code> — не начислять.",
        reply_markup=cancel_kb,
    )
    await callback.answer()


@router.callback_query(F.data == "admin:referral:cancel")
async def callback_admin_referral_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return
    await state.clear()
    inv, ref = get_referral_bonus_amounts()
    await _safe_edit(
        callback.message,
        _admin_referral_text(),
        reply_markup=admin_referral_kb(enabled=is_referral_program_enabled(), inviter=inv, referee=ref),
    )
    await callback.answer()


@router.message(AdminReferral.inviter_bonus, F.text)
async def admin_referral_inviter_save(message: Message, state: FSMContext) -> None:
    if not _settings_access(message.from_user.id):
        await state.clear()
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("⚠️ Нужно целое число ≥ 0")
        return
    set_referral_bonus_inviter(int(raw))
    await state.clear()
    await message.answer(
        "✅ <b>Сохранено</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🤝 К реферальной программе", callback_data="admin:settings:referral")]]
        ),
    )


@router.message(AdminReferral.referee_bonus, F.text)
async def admin_referral_referee_save(message: Message, state: FSMContext) -> None:
    if not _settings_access(message.from_user.id):
        await state.clear()
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("⚠️ Нужно целое число ≥ 0")
        return
    set_referral_bonus_referee(int(raw))
    await state.clear()
    await message.answer(
        "✅ <b>Сохранено</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🤝 К реферальной программе", callback_data="admin:settings:referral")]]
        ),
    )


@router.message(AdminBusinessHours.start_time, F.text)
async def admin_business_hours_set_start(message: Message, state: FSMContext) -> None:
    if not _settings_access(message.from_user.id):
        await state.clear()
        return
    ok, err = set_business_hours_time(start=(message.text or "").strip())
    if not ok:
        await message.answer(f"⚠️ {err}")
        return
    await state.clear()
    await message.answer(
        "✅ <b>Время начала сохранено</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🕐 К экрану времени работы", callback_data="admin:settings:business_hours")]]
        ),
    )


@router.message(AdminBusinessHours.end_time, F.text)
async def admin_business_hours_set_end(message: Message, state: FSMContext) -> None:
    if not _settings_access(message.from_user.id):
        await state.clear()
        return
    ok, err = set_business_hours_time(end=(message.text or "").strip())
    if not ok:
        await message.answer(f"⚠️ {err}")
        return
    await state.clear()
    await message.answer(
        "✅ <b>Время окончания сохранено</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🕐 К экрану времени работы", callback_data="admin:settings:business_hours")]]
        ),
    )


@router.callback_query(F.data == "admin:notif:new")
async def callback_admin_notif_new(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return

    await state.set_state(AdminNotifications.admin_new_order_template)
    await callback.message.answer(
        "📨 <b>Шаблон уведомления админу о новом заказе</b>\n\n"
        "Отправьте новый текст шаблона.\n\n"
        "📋 <b>Текущий шаблон:</b>\n"
        f"{get_admin_new_order_template()}",
        reply_markup=_get_admin_settings_notif_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:notif:status")
async def callback_admin_notif_status(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return

    await state.set_state(AdminNotifications.user_status_template)
    await callback.message.answer(
        "📬 <b>Шаблон уведомления клиенту о статусе заказа</b>\n\n"
        "Отправьте новый текст шаблона.\n\n"
        "📋 <b>Текущий шаблон:</b>\n"
        f"{get_user_status_template()}",
        reply_markup=_get_admin_settings_notif_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:notif:chat")
async def callback_admin_notif_chat(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return

    await state.set_state(AdminNotifications.notify_chat_id)
    await callback.message.answer(
        "📢 <b>Лог-чат для уведомлений о заказах</b>\n\n"
        "Отправьте <code>chat_id</code> чата (например: <code>-1001234567890</code>).\n"
        "Чтобы отключить — отправьте: <code>off</code>",
        reply_markup=_get_admin_settings_notif_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:notif:start_cmd")
async def callback_admin_notif_start_cmd(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return

    await state.set_state(AdminNotifications.start_command_description)
    await callback.message.answer(
        "⌨️ <b>Текст команды /start</b>\n\n"
        "Отправьте новый текст описания команды /start в меню Telegram.\n\n"
        "📋 <b>Текущее значение:</b>\n"
        f"{get_start_command_description()}",
        reply_markup=_get_admin_settings_notif_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:notif:client_toggle")
async def callback_admin_notif_client_toggle(callback: CallbackQuery) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return

    set_user_status_notification_enabled(not is_user_status_notification_enabled())
    await _safe_edit(
        callback.message,
        _admin_settings_notifications_text(),
        reply_markup=_get_admin_settings_notif_kb(),
    )
    await callback.answer("✅ Сохранено")


@router.callback_query(F.data == "admin:db:backup")
async def callback_admin_db_backup(callback: CallbackQuery) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(tempfile.gettempdir(), f"shop_backup_{stamp}.sqlite")
    try:
        with sqlite3.connect(path_to_db) as src, sqlite3.connect(backup_path) as dst:
            src.backup(dst)

        await callback.message.answer_document(
            FSInputFile(backup_path, filename=f"shop_backup_{stamp}.sqlite"),
            caption=ui_panel(
                emoji="✅",
                title="Бэкап базы",
                intro="Файл SQLite готов к сохранению на вашем устройстве.",
                body_lines=[f"🗓 <b>Метка времени:</b> <code>{stamp}</code>"],
            ),
            reply_markup=_service_back_kb(),
        )
        await callback.answer("✅ Бэкап отправлен")
    except Exception:
        await callback.answer("❌ Не удалось создать бэкап", show_alert=True)
    finally:
        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
        except Exception:
            pass


def _is_valid_sqlite_file(file_path: str) -> bool:
    try:
        with sqlite3.connect(file_path) as conn:
            conn.execute("SELECT 1 FROM sqlite_master LIMIT 1")
    except sqlite3.Error:
        return False
    return True


_DB_UPLOAD_MAX_BYTES = 80 * 1024 * 1024


@router.callback_query(F.data == "admin:db:delete_with_backup")
async def callback_admin_db_delete_with_backup(callback: CallbackQuery) -> None:
    if not is_owner_user(callback.from_user.id):
        await callback.answer("Только владелец", show_alert=True)
        return
    if not os.path.isfile(path_to_db):
        await callback.answer("Файл базы не найден", show_alert=True)
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(tempfile.gettempdir(), f"shop_before_delete_{stamp}.sqlite")
    try:
        with sqlite3.connect(path_to_db) as src, sqlite3.connect(backup_path) as dst:
            src.backup(dst)

        await callback.message.answer_document(
            FSInputFile(backup_path, filename=f"shop_backup_BEFORE_DELETE_{stamp}.sqlite"),
            caption=ui_panel(
                emoji="⚠️",
                title="Копия перед удалением",
                intro="Сохраните файл. Далее рабочая база будет удалена и создана пустая.",
                body_lines=[f"🗓 <code>{stamp}</code>"],
            ),
            reply_markup=_service_back_kb(),
        )
    except Exception:
        await callback.answer("❌ Не удалось снять бэкап", show_alert=True)
        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
        except Exception:
            pass
        return
    finally:
        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
        except Exception:
            pass

    try:
        os.remove(path_to_db)
    except OSError:
        await callback.message.answer(
            "⚠️ <b>Не удалось удалить файл базы</b>\n──────────────\n"
            "Файл, вероятно, занят процессом. Сохраните присланный бэкап, остановите бота и удалите файл вручную, "
            f"затем запустите снова — таблицы создадутся автоматически.\n\n<code>{html.escape(path_to_db)}</code>",
            reply_markup=_service_back_kb(),
        )
        await callback.answer()
        return

    init_shop_tables()
    await callback.message.answer(
        "✅ <b>База сброшена</b>\n──────────────\n"
        "Создана новая пустая база с таблицами. <b>Рекомендуется перезапустить бота.</b>",
        reply_markup=_service_back_kb(),
    )
    await callback.answer("Готово")


@router.callback_query(F.data == "admin:db:upload")
async def callback_admin_db_upload_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_owner_user(callback.from_user.id):
        await callback.answer("Только владелец", show_alert=True)
        return
    await state.set_state(AdminDatabaseUpload.file)
    await callback.message.answer(
        "📤 <b>Загрузка базы</b>\n──────────────\n"
        "Отправьте файл <code>.sqlite</code> или <code>.db</code> <b>как документ</b>.\n\n"
        "Сначала будет сделан и отправлен бэкап текущей базы, затем файл будет заменён.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅ Отмена", callback_data="admin:db:upload_cancel")]]
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:db:upload_cancel")
async def callback_admin_db_upload_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_owner_user(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await callback.message.answer("Отменено.", reply_markup=_service_back_kb())
    await callback.answer()


@router.message(AdminDatabaseUpload.file, F.document)
async def admin_db_upload_file(message: Message, state: FSMContext) -> None:
    if not is_owner_user(message.from_user.id):
        await state.clear()
        return

    doc = message.document
    if not doc.file_name:
        await message.answer("Укажите имя файла с расширением .sqlite или .db", reply_markup=_service_back_kb())
        await state.clear()
        return

    low = doc.file_name.lower()
    if not (low.endswith(".sqlite") or low.endswith(".db")):
        await message.answer(
            "<b>Нужен файл</b> с расширением <code>.sqlite</code> или <code>.db</code>.",
            reply_markup=_service_back_kb(),
        )
        await state.clear()
        return

    if doc.file_size and doc.file_size > _DB_UPLOAD_MAX_BYTES:
        await message.answer(
            f"<b>Слишком большой файл</b> (лимит {_DB_UPLOAD_MAX_BYTES // (1024 * 1024)} МБ).",
            reply_markup=_service_back_kb(),
        )
        await state.clear()
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_upload = os.path.join(tempfile.gettempdir(), f"shop_upload_{stamp}_{message.from_user.id}.sqlite")

    try:
        file_info = await message.bot.get_file(doc.file_id)
        downloaded = await message.bot.download_file(file_info.file_path)
        raw = downloaded.read()
        with open(tmp_upload, "wb") as f:
            f.write(raw)
    except Exception as exc:
        await message.answer(
            f"<b>Не удалось скачать файл</b>\n<code>{html.escape(str(exc)[:400])}</code>",
            reply_markup=_service_back_kb(),
        )
        await state.clear()
        return

    if not _is_valid_sqlite_file(tmp_upload):
        try:
            os.remove(tmp_upload)
        except Exception:
            pass
        await message.answer("<b>Файл не похож на SQLite</b>", reply_markup=_service_back_kb())
        await state.clear()
        return

    db_abs = os.path.abspath(path_to_db)
    os.makedirs(os.path.dirname(db_abs) or ".", exist_ok=True)

    pre_backup = os.path.join(tempfile.gettempdir(), f"shop_before_upload_{stamp}.sqlite")
    try:
        if os.path.isfile(db_abs):
            with sqlite3.connect(db_abs) as src, sqlite3.connect(pre_backup) as dst:
                src.backup(dst)
            await message.answer_document(
                FSInputFile(pre_backup, filename=f"shop_backup_BEFORE_UPLOAD_{stamp}.sqlite"),
                caption=ui_panel(
                    emoji="💾",
                    title="Бэкап перед заменой",
                    intro="Текущая база сохранена. Далее будет подставлен загруженный файл.",
                    body_lines=[f"🗓 <code>{stamp}</code>"],
                ),
                reply_markup=_service_back_kb(),
            )
    except Exception as exc:
        try:
            os.remove(tmp_upload)
        except Exception:
            pass
        try:
            if os.path.exists(pre_backup):
                os.remove(pre_backup)
        except Exception:
            pass
        await message.answer(
            f"<b>Не удалось снять бэкап текущей базы</b>\n<code>{html.escape(str(exc)[:400])}</code>",
            reply_markup=_service_back_kb(),
        )
        await state.clear()
        return
    finally:
        try:
            if os.path.exists(pre_backup):
                os.remove(pre_backup)
        except Exception:
            pass

    swap = db_abs + ".was_replaced"
    try:
        if os.path.isfile(db_abs):
            os.replace(db_abs, swap)
        shutil.copy2(tmp_upload, db_abs)
    except Exception as exc:
        if os.path.isfile(swap):
            try:
                os.replace(swap, db_abs)
            except OSError:
                pass
        try:
            os.remove(tmp_upload)
        except Exception:
            pass
        await message.answer(
            f"<b>Не удалось заменить файл базы</b>\n<code>{html.escape(str(exc)[:400])}</code>",
            reply_markup=_service_back_kb(),
        )
        await state.clear()
        return
    else:
        if os.path.isfile(swap):
            try:
                os.remove(swap)
            except OSError:
                pass

    try:
        os.remove(tmp_upload)
    except Exception:
        pass

    init_shop_tables()
    await state.clear()
    await message.answer(
        "✅ <b>База заменена</b>\n──────────────\n"
        "Таблицы проверены/обновлены. <b>Рекомендуется перезапустить бота.</b>",
        reply_markup=_service_back_kb(),
    )


@router.message(AdminDatabaseUpload.file)
async def admin_db_upload_wrong_kind(message: Message, state: FSMContext) -> None:
    if not is_owner_user(message.from_user.id):
        return
    await message.answer(
        "Отправьте файл базы <b>как документ</b> (.sqlite или .db).",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅ Отмена", callback_data="admin:db:upload_cancel")]]
        ),
    )


@router.message(AdminNotifications.admin_new_order_template)
async def set_admin_new_order_tpl(message: Message, state: FSMContext) -> None:
    if not _settings_access(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer(
            "<b>⚠ Пустой шаблон</b>\n\n<i>Введите текст уведомления.</i>",
            reply_markup=_get_admin_settings_notif_kb(),
        )
        return

    set_admin_new_order_template(text)
    await state.clear()
    await message.answer("✅ <b>Шаблон уведомления админу обновлён!</b>", reply_markup=_get_admin_settings_notif_kb())


@router.message(AdminNotifications.user_status_template)
async def set_user_status_tpl(message: Message, state: FSMContext) -> None:
    if not _settings_access(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer(
            "<b>⚠ Пустой шаблон</b>\n\n<i>Введите текст для клиента.</i>",
            reply_markup=_get_admin_settings_notif_kb(),
        )
        return

    set_user_status_template(text)
    await state.clear()
    await message.answer("✅ <b>Шаблон уведомления клиенту обновлён!</b>", reply_markup=_get_admin_settings_notif_kb())


@router.message(AdminNotifications.notify_chat_id)
async def set_notify_chat(message: Message, state: FSMContext) -> None:
    if not _settings_access(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    if text.lower() == "off":
        set_notify_chat_id("")
        await state.clear()
        await message.answer("🔕 <b>Лог-чат отключён.</b>", reply_markup=_get_admin_settings_notif_kb())
        return

    try:
        int(text)
    except ValueError:
        await message.answer(
            "<b>⚠ Неверный chat_id</b>\n\n"
            "Пример: <code>-1001234567890</code>\n"
            "<i>Чтобы отключить — отправьте <code>off</code></i>",
            reply_markup=_get_admin_settings_notif_kb(),
        )
        return

    set_notify_chat_id(text)
    await state.clear()
    await message.answer("✅ <b>Лог-чат сохранён!</b>", reply_markup=_get_admin_settings_notif_kb())


@router.message(AdminNotifications.start_command_description)
async def set_start_cmd_description(message: Message, state: FSMContext) -> None:
    if not _settings_access(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer(
            "<b>⚠ Пустое значение</b>\n\n<i>Введите текст для команды /start.</i>",
            reply_markup=_get_admin_settings_notif_kb(),
        )
        return

    set_start_command_description(text)
    await set_default_commands(message.bot)
    await state.clear()
    await message.answer("✅ <b>Текст команды /start обновлён!</b>", reply_markup=_get_admin_settings_notif_kb())


@router.callback_query(F.data == "admin:pay:card")
async def callback_admin_pay_card(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return

    await state.set_state(AdminPayments.card)
    current = get_payment_info("card") or "не настроено"
    await callback.message.answer(
        "💳 <b>Оплата банковской картой</b>\n\n"
        "Отправьте реквизиты (номер карты, получатель и т.д.).\n"
        "Чтобы отключить — отправьте: <code>off</code>\n\n"
        "📋 <b>Текущие реквизиты:</b>\n"
        f"{current}",
        reply_markup=_get_admin_settings_payments_kb(callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:pay:cod:toggle")
async def callback_admin_pay_cod_toggle(callback: CallbackQuery) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return

    current = is_payment_enabled("cod")
    set_payment_enabled("cod", not current)
    status = "✅ включён" if not current else "❌ выключен"
    await _safe_edit(
        callback.message,
        _admin_settings_payments_text(),
        reply_markup=_get_admin_settings_payments_kb(callback.from_user.id),
    )
    await callback.answer(f"🚚 Наложенный платёж {status}")


@router.callback_query(F.data == "admin:pay:applepay")
async def callback_admin_pay_apple(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return

    await state.set_state(AdminPayments.applepay)
    current = get_payment_info("applepay") or "не настроено"
    await callback.message.answer(
        "🍏 <b>Apple Pay</b>\n\n"
        "Отправьте инструкцию или ссылку для оплаты через Apple Pay.\n"
        "Чтобы отключить — отправьте: <code>off</code>\n\n"
        "📋 <b>Текущее значение:</b>\n"
        f"{current}",
        reply_markup=_get_admin_settings_payments_kb(callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:pay:googlepay")
async def callback_admin_pay_google(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return

    await state.set_state(AdminPayments.googlepay)
    current = get_payment_info("googlepay") or "не настроено"
    await callback.message.answer(
        "🤖 <b>Google Pay</b>\n\n"
        "Отправьте инструкцию или ссылку для оплаты через Google Pay.\n"
        "Чтобы отключить — отправьте: <code>off</code>\n\n"
        "📋 <b>Текущее значение:</b>\n"
        f"{current}",
        reply_markup=_get_admin_settings_payments_kb(callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:pay:crypto:toggle")
async def callback_admin_pay_crypto_toggle(callback: CallbackQuery) -> None:
    if not _settings_access(callback.from_user.id):
        await callback.answer("Нет доступа к настройкам", show_alert=True)
        return

    if not get_cryptobot_token():
        await callback.answer("Сначала задайте CryptoBot API токен", show_alert=True)
        return

    new_state = not is_payment_enabled("crypto")
    set_payment_enabled("crypto", new_state)
    await _safe_edit(
        callback.message,
        _admin_settings_payments_text(),
        reply_markup=_get_admin_settings_payments_kb(callback.from_user.id),
    )
    await callback.answer("🪙 CryptoBot включён" if new_state else "🪙 CryptoBot выключен")


@router.callback_query(F.data == "admin:pay:crypto_token")
async def callback_admin_pay_crypto_token(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_owner_user(callback.from_user.id):
        await callback.answer("Только главный админ может менять API токен", show_alert=True)
        return

    await state.set_state(AdminPayments.crypto_token)
    has_token = bool(get_cryptobot_token())
    cur = "✅ задан" if has_token else "➖ не задан"
    await callback.message.answer(
        "🔑 <b>CryptoBot API токен</b>\n\n"
        "Нужен для автоматического создания счетов и проверки оплаты.\n"
        f"Текущий: <b>{cur}</b>\n\n"
        "Отправьте новый токен одной строкой.\n"
        "Чтобы отключить авто‑счета — отправьте <code>off</code>.",
        reply_markup=_get_admin_settings_payments_kb(callback.from_user.id),
    )
    await callback.answer()


@router.message(AdminPayments.card)
async def set_pay_card(message: Message, state: FSMContext) -> None:
    if not _settings_access(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    set_payment_setting("card", "" if text.lower() == "off" else text)
    await state.clear()
    await message.answer(
        "✅ <b>Реквизиты банковской карты обновлены!</b>",
        reply_markup=_get_admin_settings_payments_kb(message.from_user.id),
    )


@router.message(AdminPayments.applepay)
async def set_pay_apple(message: Message, state: FSMContext) -> None:
    if not _settings_access(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    set_payment_setting("applepay", "" if text.lower() == "off" else text)
    await state.clear()
    await message.answer(
        "✅ <b>Настройки Apple Pay обновлены!</b>",
        reply_markup=_get_admin_settings_payments_kb(message.from_user.id),
    )


@router.message(AdminPayments.googlepay)
async def set_pay_google(message: Message, state: FSMContext) -> None:
    if not _settings_access(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    set_payment_setting("googlepay", "" if text.lower() == "off" else text)
    await state.clear()
    await message.answer(
        "✅ <b>Настройки Google Pay обновлены!</b>",
        reply_markup=_get_admin_settings_payments_kb(message.from_user.id),
    )


@router.message(AdminPayments.crypto)
async def set_pay_crypto(message: Message, state: FSMContext) -> None:
    if not _settings_access(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    set_payment_setting("crypto", "" if text.lower() == "off" else text)
    await state.clear()
    await message.answer(
        "✅ <b>Настройки CryptoBot обновлены!</b>",
        reply_markup=_get_admin_settings_payments_kb(message.from_user.id),
    )


async def _restart_bot_after_cryptobot_token_change(message: Message) -> None:
    """Токен в БД уже сохранён; перезапуск процесса — как admin:bot:restart."""
    await message.answer(
        "<b>♻️ Перезапуск бота</b>\n──────────────\n"
        "<i>Токен CryptoBot применён. Останавливаю приём обновлений и запускаю новый процесс…</i>",
        reply_markup=_get_admin_settings_payments_kb(message.from_user.id),
    )
    mark_restart_requested()
    try:
        await dispatcher.stop_polling()
    except Exception as exc:
        cancel_restart_request()
        try:
            await message.answer(
                f"<b>⚠ Не удалось перезапустить бота</b>\n<code>{html.escape(str(exc)[:300])}</code>",
                reply_markup=_get_admin_settings_payments_kb(message.from_user.id),
            )
        except Exception:
            pass


@router.message(AdminPayments.crypto_token)
async def set_pay_crypto_token(message: Message, state: FSMContext) -> None:
    if not is_owner_user(message.from_user.id):
        await state.clear()
        return
    text = (message.text or "").strip()
    old_token = get_cryptobot_token()
    if text.lower() == "off":
        set_cryptobot_token("")
        await state.clear()
        await message.answer(
            "🔕 <b>CryptoBot API токен отключён</b>\n<i>Авто‑счета и авто‑проверка оплат выключены.</i>",
            reply_markup=_get_admin_settings_payments_kb(message.from_user.id),
        )
        if old_token.strip():
            await _restart_bot_after_cryptobot_token_change(message)
        return
    if not text or len(text) < 10:
        await message.answer(
            "<b>⚠ Похоже на некорректный токен</b>\nОтправьте токен одной строкой или <code>off</code>.",
            reply_markup=_get_admin_settings_payments_kb(message.from_user.id),
        )
        return
    set_cryptobot_token(text)
    await state.clear()
    await message.answer(
        "✅ <b>CryptoBot API токен сохранён</b>\n<i>Теперь бот сможет создавать инвойсы и подтверждать оплату автоматически.</i>",
        reply_markup=_get_admin_settings_payments_kb(message.from_user.id),
    )
    if text.strip() != old_token.strip():
        await _restart_bot_after_cryptobot_token_change(message)
