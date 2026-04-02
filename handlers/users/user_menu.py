import datetime
import os
import sqlite3
import tempfile

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from data.config import adm, bot_description
from keyboards.inline.user_inline import (
    admin_settings_inline_kb,
    admin_menu_inline_kb,
    admin_reply_cancel_kb,
    main_menu_inline_kb,
    profile_actions_inline_kb,
    support_back_inline_kb,
    support_menu_inline_kb,
    support_tickets_list_kb,
    support_ticket_view_kb,
)
from handlers.users.shop_state import AdminNotifications, AdminPayments, SupportDialog
from utils.db_api.shop import get_user_profile as get_shop_user_profile
from utils.db_api.shop import ensure_user
from utils.db_api.shop import (
    get_admin_ids,
    get_admin_new_order_template,
    get_notify_chat_id,
    get_payment_info,
    get_support_admin_ids,
    get_shop_stats,
    get_user_status_template,
    get_welcome_message,
    is_admin_user,
    is_payment_enabled,
    is_maintenance,
    is_owner_user,
    is_support_admin,
    create_support_ticket,
    get_support_tickets,
    get_support_ticket,
    close_support_ticket,
    delete_old_closed_tickets,
    set_admin_new_order_template,
    set_notify_chat_id,
    set_payment_enabled,
    set_payment_setting,
    set_user_status_template,
)
from utils.db_api.sqlite import get_all_categoriesx, get_userx
from utils.db_api.sqlite import path_to_db

router = Router(name="user_menu")
# Compatibility export for legacy imports expecting `dp` symbol.
dp = router


def _is_admin(user_id: int) -> bool:
    return is_admin_user(user_id)


def _get_admin_menu_kb():
    return admin_menu_inline_kb(maintenance_enabled=is_maintenance())


def _get_admin_settings_kb():
    return admin_settings_inline_kb(
        cod_enabled=is_payment_enabled("cod"),
        card_enabled=bool(get_payment_info("card")),
        applepay_enabled=bool(get_payment_info("applepay")),
        googlepay_enabled=bool(get_payment_info("googlepay"))
    )


def _admin_settings_text() -> str:
    chat_id = get_notify_chat_id() or "не задан"
    cod = "включен" if is_payment_enabled("cod") else "выключен"
    card = "настроена" if get_payment_info("card") else "не настроена"
    apple = "настроен" if get_payment_info("applepay") else "не настроен"
    google = "настроен" if get_payment_info("googlepay") else "не настроен"
    return (
        "<b>Настройки уведомлений и оплаты</b>\n"
        f"Лог-чат заказов: <code>{chat_id}</code>\n"
        f"Наложенный платеж: <b>{cod}</b>\n"
        f"Карта: <b>{card}</b>\n"
        f"Apple Pay: <b>{apple}</b>\n"
        f"Google Pay: <b>{google}</b>\n"
        "\nДоступные плейсхолдеры шаблонов:\n"
        "<code>{order_id}</code> <code>{status}</code> <code>{name}</code>\n"
        "<code>{phone}</code> <code>{total}</code> <code>{delivery}</code> <code>{payment}</code>"
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
    welcome_text, welcome_photo = get_welcome_message()
    if is_maintenance() and not _is_admin(message.from_user.id):
        welcome_text = f"{welcome_text}\n\n<b>🛠 Магазин временно на техработах</b>"

    if welcome_photo:
        await message.answer_photo(
            welcome_photo,
            caption=welcome_text,
            reply_markup=main_menu_inline_kb(is_admin=_is_admin(message.from_user.id)),
        )
    else:
        await message.answer(
            welcome_text,
            reply_markup=main_menu_inline_kb(is_admin=_is_admin(message.from_user.id)),
        )


@router.callback_query(F.data == "menu:main")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _safe_edit(
        callback.message,
        "<b>Главное меню</b>",
        reply_markup=main_menu_inline_kb(is_admin=_is_admin(callback.from_user.id)),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:accounts")
async def callback_accounts(callback: CallbackQuery) -> None:
    await _safe_edit(callback.message, "<b>Откройте раздел Каталог.</b>")
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
        f"<b>Категория:</b> {category_name}\n"
        "Детальная выдача перенесена в новый flow и будет добавлена отдельным модулем.",
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
    user = get_userx(user_id=callback.from_user.id)
    username = callback.from_user.first_name or callback.from_user.username or "не указан"
    full_name = (profile.get("name") or "").strip() or "не заполнено"
    reg_date = profile.get("created_at") or (user[6] if user and len(user) > 6 else "-")
    phone = profile["phone"] if profile["phone"] else "не указан"
    address = profile["address"] if profile["address"] else "не указан"
    bonus = profile.get("bonus", 0)
    bonus_line = f"🎁 Бонус: <b>{bonus} грн</b>\n" if bonus > 0 else ""
    profile_text = (
        "<b>👤 Личный кабинет</b>\n"
        f"🆔 ID: <code>{callback.from_user.id}</code>\n"
        f"🔖 Username: <b>{username}</b>\n"
        f"🙍 ФИО: <b>{full_name}</b>\n"
        f"📞 Телефон: <b>{phone}</b>\n"
        f"📍 Адрес: <b>{address}</b>\n"
        f"{bonus_line}"
        f"📅 Регистрация: <b>{reg_date}</b>"
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
    await _safe_edit(
        callback.message,
        "<b>Главное меню</b>",
        reply_markup=main_menu_inline_kb(is_admin=_is_admin(callback.from_user.id)),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:support")
async def callback_support_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _safe_edit(
        callback.message,
        "<b>🛟 Техническая поддержка</b>\n"
        "Если есть вопрос по заказу или работе бота, напишите нам в поддержку.\n\n"
        "Мы ответим вам в ближайшее время.",
        reply_markup=support_menu_inline_kb,
    )
    await callback.answer()


@router.callback_query(F.data == "support:start")
async def callback_support_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SupportDialog.user_message)
    await _safe_edit(
        callback.message,
        "🛟 <b>Опишите суть проблемы:</b>",
        reply_markup=support_back_inline_kb,
    )
    await callback.answer()


@router.message(SupportDialog.user_message)
async def support_user_message_send(message: Message, state: FSMContext) -> None:
    text_body = (message.text or message.caption or "").strip()
    has_photo = bool(message.photo)
    has_document = bool(message.document)

    if not text_body and not has_photo and not has_document:
        await message.answer("Отправьте текст, фото или файл")
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
        inline_keyboard=[[InlineKeyboardButton(text="↩️ Ответить клиенту", callback_data=f"support:reply:{ticket_id}")]]
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
            "🛟 <b>Ваше обращение принято!</b>\n\nС вами скоро свяжутся.\n\n<i>Тех. поддержка</i>",
            reply_markup=support_menu_inline_kb,
        )
        return
    await message.answer(
        "🛟 <b>Ваше обращение принято!</b>\n\nС вами скоро свяжутся.\n\n<i>Тех. поддержка</i>",
        reply_markup=support_menu_inline_kb,
    )


@router.callback_query(F.data.startswith("support:reply:"))
async def support_admin_reply_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    if not (is_owner_user(callback.from_user.id) or is_support_admin(callback.from_user.id)):
        await callback.answer("Вы не назначены в техподдержку", show_alert=True)
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
        f"✍️ Введите ответ для клиента <b>{first_name}</b> (обращение #{ticket_id}):",
        reply_markup=admin_reply_cancel_kb,
    )
    await callback.answer()


@router.message(SupportDialog.admin_reply)
async def support_admin_reply_send(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await state.clear()
        return
    if not (is_owner_user(message.from_user.id) or is_support_admin(message.from_user.id)):
        await state.clear()
        await message.answer("Вы не назначены в техподдержку")
        return

    text_body = (message.text or message.caption or "").strip()
    has_photo = bool(message.photo)
    has_document = bool(message.document)

    if not text_body and not has_photo and not has_document:
        await message.answer("Введите текст, фото или файл для ответа")
        return

    data = await state.get_data()
    target_user_id = int(data.get("support_target_user_id", 0) or 0)
    ticket_id_done = int(data.get("support_ticket_id", 0) or 0)
    if not target_user_id:
        await state.clear()
        await message.answer("Не удалось определить клиента")
        return

    reply_header = "<b>🛟 Ответ техподдержки</b>\n"

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
        await message.answer("❌ Не удалось отправить ответ клиенту")
        return

    await state.clear()
    await message.answer(
        "✅ Ответ отправлен клиенту",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="⬅ К обращениям", callback_data=f"admin:ticket:{ticket_id_done}" if ticket_id_done else "admin:support_tickets"),
            ]]
        ),
    )


@router.callback_query(F.data == "admin:support_tickets")
async def callback_admin_support_tickets(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    tickets = get_support_tickets(status="active")
    active = len(tickets)
    closed = len(get_support_tickets(status="closed"))

    if not tickets:
        text = (
            "<b>🛟 Обращения в техподдержку</b>\n"
            f"🟢 Активных: <b>{active}</b>  🔴 Завершенных: <b>{closed}</b>\n\n"
            "Активных обращений пока нет."
        )
    else:
        text = (
            f"<b>🛟 Обращения в техподдержку</b>\n"
            f"🟢 Активных: <b>{active}</b>  🔴 Завершенных: <b>{closed}</b>\n\n"
            "Выберите активное обращение:"
        )

    await _safe_edit(callback.message, text, reply_markup=support_tickets_list_kb(tickets, show_closed=False))
    await callback.answer()


@router.callback_query(F.data == "admin:support_tickets:closed")
async def callback_admin_support_tickets_closed(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    tickets = get_support_tickets(status="closed")
    active = len(get_support_tickets(status="active"))
    closed = len(tickets)

    if not tickets:
        text = (
            "<b>📁 Завершенные обращения</b>\n"
            f"🟢 Активных: <b>{active}</b>  🔴 Завершенных: <b>{closed}</b>\n\n"
            "Завершенных обращений пока нет."
        )
    else:
        text = (
            "<b>📁 Завершенные обращения</b>\n"
            f"🟢 Активных: <b>{active}</b>  🔴 Завершенных: <b>{closed}</b>\n\n"
            "Выберите обращение:"
        )

    await _safe_edit(callback.message, text, reply_markup=support_tickets_list_kb(tickets, show_closed=True))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:ticket:close:"))
async def callback_admin_ticket_close(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
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
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
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
                await callback.message.answer_photo(media_file_id, caption=f"🧾 Вложение к обращению #{ticket_id}")
            else:
                await callback.message.answer_document(media_file_id, caption=f"🧾 Вложение к обращению #{ticket_id}")
        except Exception:
            pass

    await _safe_edit(callback.message, text, reply_markup=support_ticket_view_kb(ticket_id, ticket["status"]))
    await callback.answer()


@router.callback_query(F.data == "menu:admin")
async def callback_admin_menu(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await _safe_edit(callback.message, "<b>Админ меню</b>", reply_markup=_get_admin_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:bot_info")
async def callback_admin_bot_info(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    stats = get_shop_stats()
    text = (
        "<b>📊 Информация о боте</b>\n\n"
        "<b>Система:</b>\n"
        f"🤖 ID бота: <code>{callback.bot.id}</code>\n"
        f"👤 Ваш ID: <code>{callback.from_user.id}</code>\n\n"
        "<b>Магазин:</b>\n"
        f"👥 Клиентов: <b>{stats['customers']}</b>\n"
        f"⚙️ Администраторов: <b>{stats['admins']}</b>\n\n"
        "<b>Товары:</b>\n"
        f"📁 Категорий: <b>{stats['categories']}</b>\n"
        f"📦 Товаров: <b>{stats['products']}</b>\n\n"
        "<b>Заказы:</b>\n"
        f"🆕 Новых: <b>{stats['orders_new']}</b>\n"
        f"⚡ В работе: <b>{stats['orders_inwork']}</b>\n"
        f"📂 В архиве: <b>{stats['orders_archive']}</b>\n"
        f"📊 Всего: <b>{stats['orders']}</b>\n\n"
        f"💰 Выручка: <b>{stats['revenue']:,}</b> грн"
    )

    await _safe_edit(
        callback.message,
        text,
        reply_markup=_get_admin_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:settings")
async def callback_admin_settings(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await _safe_edit(
        callback.message,
        _admin_settings_text(),
        reply_markup=_get_admin_settings_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:notif:new")
async def callback_admin_notif_new(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(AdminNotifications.admin_new_order_template)
    await callback.message.answer(
        "Отправьте новый шаблон уведомления админу о заказе.\n"
        "Текущий шаблон:\n"
        f"{get_admin_new_order_template()}"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:notif:status")
async def callback_admin_notif_status(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(AdminNotifications.user_status_template)
    await callback.message.answer(
        "Отправьте новый шаблон уведомления клиенту о статусе заказа.\n"
        "Текущий шаблон:\n"
        f"{get_user_status_template()}"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:notif:chat")
async def callback_admin_notif_chat(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(AdminNotifications.notify_chat_id)
    await callback.message.answer(
        "Отправьте chat_id для логов заказов (например, -1001234567890).\n"
        "Чтобы отключить лог-чат, отправьте: <code>off</code>."
    )
    await callback.answer()


@router.callback_query(F.data == "admin:db:backup")
async def callback_admin_db_backup(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(tempfile.gettempdir(), f"shop_backup_{stamp}.sqlite")
    try:
        with sqlite3.connect(path_to_db) as src, sqlite3.connect(backup_path) as dst:
            src.backup(dst)

        await callback.message.answer_document(
            FSInputFile(backup_path, filename=f"shop_backup_{stamp}.sqlite"),
            caption="✅ Бэкап БД сформирован",
        )
        await callback.answer("Бэкап отправлен")
    except Exception:
        await callback.answer("Не удалось создать бэкап", show_alert=True)
    finally:
        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
        except Exception:
            pass


@router.message(AdminNotifications.admin_new_order_template)
async def set_admin_new_order_tpl(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Шаблон не может быть пустым")
        return

    set_admin_new_order_template(text)
    await state.clear()
    await message.answer("Шаблон уведомления админу обновлен.", reply_markup=_get_admin_settings_kb())


@router.message(AdminNotifications.user_status_template)
async def set_user_status_tpl(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Шаблон не может быть пустым")
        return

    set_user_status_template(text)
    await state.clear()
    await message.answer("Шаблон уведомления клиенту обновлен.", reply_markup=_get_admin_settings_kb())


@router.message(AdminNotifications.notify_chat_id)
async def set_notify_chat(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    if text.lower() == "off":
        set_notify_chat_id("")
        await state.clear()
        await message.answer("Лог-чат отключен.", reply_markup=_get_admin_settings_kb())
        return

    try:
        int(text)
    except ValueError:
        await message.answer("Неверный chat_id. Пример: <code>-1001234567890</code>")
        return

    set_notify_chat_id(text)
    await state.clear()
    await message.answer("Лог-чат сохранен.", reply_markup=_get_admin_settings_kb())


@router.callback_query(F.data == "admin:pay:card")
async def callback_admin_pay_card(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(AdminPayments.card)
    current = get_payment_info("card") or "не настроено"
    await callback.message.answer(
        "Отправьте реквизиты для оплаты банковской картой.\n"
        "Чтобы отключить способ оплаты, отправьте: <code>off</code>\n\n"
        f"Текущее значение:\n{current}"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:pay:cod:toggle")
async def callback_admin_pay_cod_toggle(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    current = is_payment_enabled("cod")
    set_payment_enabled("cod", not current)
    status = "включен" if not current else "выключен"
    await _safe_edit(callback.message, _admin_settings_text(), reply_markup=_get_admin_settings_kb())
    await callback.answer(f"Наложенный платеж {status}")


@router.callback_query(F.data == "admin:pay:applepay")
async def callback_admin_pay_apple(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(AdminPayments.applepay)
    current = get_payment_info("applepay") or "не настроено"
    await callback.message.answer(
        "Отправьте инструкцию или ссылку для Apple Pay.\n"
        "Чтобы отключить способ оплаты, отправьте: <code>off</code>\n\n"
        f"Текущее значение:\n{current}"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:pay:googlepay")
async def callback_admin_pay_google(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(AdminPayments.googlepay)
    current = get_payment_info("googlepay") or "не настроено"
    await callback.message.answer(
        "Отправьте инструкцию или ссылку для Google Pay.\n"
        "Чтобы отключить способ оплаты, отправьте: <code>off</code>\n\n"
        f"Текущее значение:\n{current}"
    )
    await callback.answer()


@router.message(AdminPayments.card)
async def set_pay_card(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    set_payment_setting("card", "" if text.lower() == "off" else text)
    await state.clear()
    await message.answer("Настройки банковской карты обновлены.", reply_markup=_get_admin_settings_kb())


@router.message(AdminPayments.applepay)
async def set_pay_apple(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    set_payment_setting("applepay", "" if text.lower() == "off" else text)
    await state.clear()
    await message.answer("Настройки Apple Pay обновлены.", reply_markup=_get_admin_settings_kb())


@router.message(AdminPayments.googlepay)
async def set_pay_google(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    set_payment_setting("googlepay", "" if text.lower() == "off" else text)
    await state.clear()
    await message.answer("Настройки Google Pay обновлены.", reply_markup=_get_admin_settings_kb())
