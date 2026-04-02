# - *- coding: utf- 8 - *-
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from data import config

bot = Bot(
	token=config.BOT_TOKEN,
	default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dispatcher = Dispatcher(storage=MemoryStorage())
# Compatibility alias for legacy imports.
dp = dispatcher
