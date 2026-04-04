"""Фоновые напоминания о незавершённой корзине."""

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from utils.db_api.shop import (
    cart_total,
    get_shop_setting,
    is_admin_user,
    is_maintenance,
    list_cart_abandon_candidate_user_ids,
    mark_cart_abandon_reminder_sent,
)

_log = logging.getLogger(__name__)


async def cart_abandon_reminder_loop(bot: Bot) -> None:
    while True:
        await asyncio.sleep(15 * 60)
        try:
            if is_maintenance():
                continue
            if get_shop_setting("cart_abandon_enabled", "1") != "1":
                continue
            try:
                hours = float((get_shop_setting("cart_abandon_hours", "3") or "3").replace(",", "."))
            except ValueError:
                hours = 3.0
            candidates = list_cart_abandon_candidate_user_ids(hours)
            if not candidates:
                continue
            kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🧺 Открыть корзину", callback_data="menu:cart")]]
            )
            text = (
                "<b>🛒 Корзина ждёт</b>\n\n"
                "Вы добавили товары, но не оформили заказ. "
                "Загляните в корзину — позиции ещё доступны."
            )
            for uid in candidates:
                if is_admin_user(int(uid)):
                    continue
                if cart_total(int(uid)) < 1:
                    continue
                try:
                    await bot.send_message(int(uid), text, reply_markup=kb)
                    mark_cart_abandon_reminder_sent(int(uid))
                except TelegramBadRequest as exc:
                    err = str(exc).lower()
                    if "blocked" in err or "deactivated" in err or "chat not found" in err:
                        mark_cart_abandon_reminder_sent(int(uid))
                    else:
                        _log.warning("cart reminder uid=%s: %s", uid, exc)
                except Exception as exc:
                    _log.warning("cart reminder uid=%s: %s", uid, exc)
        except Exception as exc:
            _log.exception("cart_abandon_reminder_loop: %s", exc)
