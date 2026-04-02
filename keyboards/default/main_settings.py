# - *- coding: utf- 8 - *-
from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from utils.db_api.sqlite import get_settingsx


def get_settings_func():
    get_settings = get_settingsx()
    builder = ReplyKeyboardBuilder()
    if get_settings[3] == "True":
        status_buy = "🔴 Выключить Выдачу"
    elif get_settings[3] == "False":
        status_buy = "🟢 Включить Выдачу"
    if get_settings[2] == "True":
        status_work = "🔴 Отправить на тех. работы"
    elif get_settings[2] == "False":
        status_work = "🟢 Вывести из тех. работ"
    builder.row(KeyboardButton(text="ℹ Изменить FAQ 🖍"))
    builder.row(KeyboardButton(text=status_work), KeyboardButton(text=status_buy))
    builder.row(KeyboardButton(text="⬅ На главную"))
    return builder.as_markup(resize_keyboard=True)
