# - *- coding: utf- 8 - *-
from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from utils.db_api.sqlite import get_paymentx


def payment_default():
    payment = get_paymentx()
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🥝 Изменить QIWI 🖍"),
        KeyboardButton(text="🥝 Проверить QIWI ♻"),
        KeyboardButton(text="🥝 Баланс QIWI 👁"),
    )
    if payment[5] == "True":
        builder.row(KeyboardButton(text="🔴 Выключить пополнения"))
    else:
        builder.row(KeyboardButton(text="🟢 Включить пополнения"))
    builder.row(KeyboardButton(text="⬅ На главную"))
    return builder.as_markup(resize_keyboard=True)
