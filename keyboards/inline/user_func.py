# - *- coding: utf- 8 - *-
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Проверка оплаты киви
def create_pay_qiwi_func(send_requests, receipt, message_id, way):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌀 Перейти к оплате", url=send_requests)],
            [
                InlineKeyboardButton(
                    text="🔄 Проверить оплату",
                    callback_data=f"Pay:{way}:{receipt}:{message_id}",
                )
            ],
        ]
    )


# Кнопки при открытии самого товара
def open_item_func(position_id, remover, category_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Получить Акаунт",
                    callback_data=f"buy_this_item:{position_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅ Вернуться ↩",
                    callback_data=f"back_buy_item_position:{remover}:{category_id}",
                )
            ],
        ]
    )


# Подтверждение покупки товара
def confirm_buy_items(position_id, get_count, message_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"xbuy_item:{position_id}:{get_count}:{message_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"not_buy_items:{message_id}",
                ),
            ]
        ]
    )
