# - *- coding: utf- 8 - *-
from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_functions_func(user_id):
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📱 Поиск профиля 🔍"), KeyboardButton(text="📢 Рассылка"))
    builder.row(KeyboardButton(text="⬅ На главную"))
    return builder.as_markup(resize_keyboard=True)


