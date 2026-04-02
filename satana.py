# - *- coding: utf- 8 - *-
import asyncio

from handlers import router
from loader import bot, dispatcher
from utils.db_api.sqlite import create_bdx
from utils.other_func import on_startup_notify
from utils.set_bot_commands import set_default_commands


async def on_startup() -> None:
    await set_default_commands(bot)
    await on_startup_notify(dispatcher)
    print("~~~~~ Бот был запущен ~~~~~")


async def main() -> None:
    create_bdx()
    dispatcher.include_router(router)
    await on_startup()
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
