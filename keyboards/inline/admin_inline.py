# - *- coding: utf- 8 - *-
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Рассылка
sure_send_ad_inl = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="yes_send_ad"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="not_send_kb"),
        ]
    ]
)

# Добавление Админов
sure_admin_ad_inl = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Добавить", callback_data="yes_admin_ad"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="no_admin_kb"),
        ]
    ]
)

# Удаление категорий
confirm_clear_category_inl = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Да, удалить все", callback_data="confirm_clear_category"),
            InlineKeyboardButton(text="✅ Нет, отменить", callback_data="cancel_clear_category"),
        ]
    ]
)

# Удаление позиций
confirm_clear_position_inl = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Да, удалить все", callback_data="confirm_clear_position"),
            InlineKeyboardButton(text="✅ Нет, отменить", callback_data="cancel_clear_position"),
        ]
    ]
)

# Удаление товаров
confirm_clear_item_inl = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Да, удалить все", callback_data="confirm_clear_item"),
            InlineKeyboardButton(text="✅ Нет, отменить", callback_data="cancel_clear_item"),
        ]
    ]
)

# Удаление товара
delete_item_inl = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔐 Удалить товар", callback_data="delete_this_item")],
    ]
)
