from aiogram import Bot
from aiogram.types import BotCommand

from utils.db_api.shop import get_start_command_description


async def set_default_commands(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start", description=get_start_command_description())
    ])
