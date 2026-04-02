# - *- coding: utf- 8 - *-
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils.db_api.sqlite import get_paymentx, get_positionx, get_itemsx, get_positionsx, get_categoryx


# Поиск профиля
def search_profile_func(user_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎊 Выдать бонус", callback_data=f"add_balance:{user_id}"),
                InlineKeyboardButton(text="📦 Изменить наличие", callback_data=f"set_balance:{user_id}"),
            ],
            [
                InlineKeyboardButton(text="📜 Его Запросы", callback_data=f"show_purchases:{user_id}"),
                InlineKeyboardButton(text="💌 Отправить СМС", callback_data=f"send_message:{user_id}"),
            ],
        ]
    )


# Способы пополнения
def choice_way_input_payment_func():
    get_payments = get_paymentx()

    if get_payments[4] == "form":
        change_qiwi_form = InlineKeyboardButton(text="✅ По форме", callback_data="...")
    else:
        change_qiwi_form = InlineKeyboardButton(text="❌ По форме", callback_data="change_payment:form")

    if get_payments[4] == "number":
        change_qiwi_number = InlineKeyboardButton(text="✅ По номеру", callback_data="...")
    else:
        change_qiwi_number = InlineKeyboardButton(text="❌ По номеру", callback_data="change_payment:number")

    if get_payments[4] == "nickname":
        change_qiwi_nickname = InlineKeyboardButton(text="✅ По никнейму", callback_data="...")
    else:
        change_qiwi_nickname = InlineKeyboardButton(text="❌ По никнейму", callback_data="change_payment:nickname")

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [change_qiwi_form, change_qiwi_number],
            [change_qiwi_nickname],
        ]
    )


# Изменение категории
def edit_category_func(category_id, remover):
    get_fat_count = len(get_positionsx("*", category_id=category_id))
    get_category = get_categoryx("*", category_id=category_id)

    messages = "<b>📜 Выберите действие с категорией 🖍</b>\n" \
               "➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n" \
               f"🏷 Название: {get_category[2]}\n" \
               f"📁 Кол-во позиций: {get_fat_count}шт"

    category_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏷 Изменить название",
                    callback_data=f"category_edit_name:{category_id}:{remover}",
                ),
                InlineKeyboardButton(
                    text="❌ Удалить",
                    callback_data=f"category_remove:{category_id}:{remover}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅ Вернуться ↩",
                    callback_data=f"back_category_edit:{remover}",
                )
            ],
        ]
    )
    return messages, category_keyboard


# Кнопки с удалением категории
def confirm_remove_func(category_id, remover):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Да, удалить",
                    callback_data=f"yes_remove_category:{category_id}:{remover}",
                ),
                InlineKeyboardButton(
                    text="✅ Нет, отменить",
                    callback_data=f"not_remove_category:{category_id}:{remover}",
                ),
            ]
        ]
    )


# Кнопки при открытии позиции для изменения
def open_edit_position_func(position_id, category_id, remover):
    get_position = get_positionx("*", position_id=position_id)
    get_items = get_itemsx("*", position_id=position_id)
    have_photo = False
    photo_text = "Отсутствует ❌"
    if len(get_position[5]) >= 5:
        have_photo = True
        photo_text = "Имеется ✅"
    messages = "<b>📁 Редактирование позиции:</b>\n" \
               "➖➖➖➖➖➖➖➖➖➖➖➖➖\n" \
               f"<b>🏷 Название:</b> {get_position[2]}\n" \
               f"<b>📦 Количество:</b> {len(get_items)}шт\n" \
               f"<b>📸 Изображение:</b> {photo_text}\n" \
               f"<b>📜 Описание:</b> \n" \
               f"{get_position[4]}\n"
    open_item_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏷 Изм. название",
                    callback_data=f"position_change_name:{position_id}:{category_id}:{remover}",
                ),
                InlineKeyboardButton(
                    text="💵 Изм. цену",
                    callback_data=f"position_change_price:{position_id}:{category_id}:{remover}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📜 Изм. описание",
                    callback_data=f"position_change_discription:{position_id}:{category_id}:{remover}",
                ),
                InlineKeyboardButton(
                    text="📸 Изм. фото",
                    callback_data=f"position_change_photo:{position_id}:{category_id}:{remover}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"position_remove_this:{position_id}:{category_id}:{remover}",
                ),
                InlineKeyboardButton(
                    text="❌ Очистить",
                    callback_data=f"position_clear_this:{position_id}:{category_id}:{remover}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅ Вернуться ↩",
                    callback_data=f"back_position_edit:{category_id}:{remover}",
                )
            ],
        ]
    )
    return messages, open_item_keyboard, have_photo


# Подтверждение удаления позиции
def confirm_remove_position_func(position_id, category_id, remover):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Да, удалить",
                    callback_data=f"yes_remove_position:{position_id}:{category_id}:{remover}",
                ),
                InlineKeyboardButton(
                    text="✅ Нет, отменить",
                    callback_data=f"not_remove_position:{position_id}:{category_id}:{remover}",
                ),
            ]
        ]
    )


# Подтверждение очистики позиции
def confirm_clear_position_func(position_id, category_id, remover):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Да, очистить",
                    callback_data=f"yes_clear_position:{position_id}:{category_id}:{remover}",
                ),
                InlineKeyboardButton(
                    text="✅ Нет, отменить",
                    callback_data=f"not_clear_position:{position_id}:{category_id}:{remover}",
                ),
            ]
        ]
    )
