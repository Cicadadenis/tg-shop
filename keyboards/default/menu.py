# - *- coding: utf- 8 - *-
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from data.config import adm


def check_user_out_func(user_id):
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🔐 Акаунты"), KeyboardButton(text="📱 Профиль"))
    builder.row(KeyboardButton(text="📯 Функции"), KeyboardButton(text="ℹ FAQ"))
    if str(user_id) in adm:
        builder.row(
            KeyboardButton(text="🔐 Управление  🖍"),
            KeyboardButton(text="📰 Информация о боте"),
        )
        builder.row(
            KeyboardButton(text="⚙ Настройки"),
            KeyboardButton(text="🔆 Общие функции"),
            KeyboardButton(text="👤 Добавление Администраторов ⚜️"),
        )
    return builder.as_markup(resize_keyboard=True)


all_back_to_main_default = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⬅ На главную")]],
    resize_keyboard=True,
)

ssaa = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✅ Добавить ", callback_data="yes_add")],
    ]
)

lic = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✅ let's go", callback_data="pr")],
    ]
)

reg_back = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="otm")],
    ]
)



_virtualsim_builder = InlineKeyboardBuilder()
_virtualsim_builder.row(
    InlineKeyboardButton(text="📲 Telegram", callback_data="proton"),
    InlineKeyboardButton(text="📲 Signal", callback_data="sig"),
)
virtualsim = _virtualsim_builder.as_markup()

_virtualsimadm_builder = InlineKeyboardBuilder()
_virtualsimadm_builder.row(
    InlineKeyboardButton(text="📲 Telegram", callback_data="proton"),
    InlineKeyboardButton(text="📲 Signal", callback_data="sig"),
)
_virtualsimadm_builder.row(InlineKeyboardButton(text="Баланс", callback_data="BBB"))
virtualsimadm = _virtualsimadm_builder.as_markup()
