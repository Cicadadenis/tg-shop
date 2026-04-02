# - *- coding: utf- 8 - *-
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

items_default = ReplyKeyboardMarkup(
	keyboard=[
		[
			KeyboardButton(text="🔐 Добавить ➕"),
			KeyboardButton(text="🔐 Изменить 🖍"),
			KeyboardButton(text="🔐 Удалить ❌"),
		],
		[
			KeyboardButton(text="📁 Создать позицию ➕"),
			KeyboardButton(text="📁 Изменить позицию 🖍"),
			KeyboardButton(text="📁 Удалить позиции ❌"),
		],
		[
			KeyboardButton(text="📜 Создать категорию ➕"),
			KeyboardButton(text="📜 Изменить категорию 🖍"),
			KeyboardButton(text="📜 Удалить категории ❌"),
		],
		[KeyboardButton(text="⬅ На главную")],
	],
	resize_keyboard=True,
)

skip_send_image_default = ReplyKeyboardMarkup(
	keyboard=[[KeyboardButton(text="📸 Пропустить")]],
	resize_keyboard=True,
)

cancel_send_image_default = ReplyKeyboardMarkup(
	keyboard=[[KeyboardButton(text="📸 Отменить")]],
	resize_keyboard=True,
)

finish_load_items_default = ReplyKeyboardMarkup(
	keyboard=[[KeyboardButton(text="📥 Закончить загрузку")]],
	resize_keyboard=True,
)
