# - *- coding: utf- 8 - *-
import asyncio

from handlers import router
from loader import bot, dispatcher
from utils.db_api.sqlite import create_bdx
from utils.db_api.shop import delete_old_closed_tickets
from utils.other_func import on_startup_notify
from utils.set_bot_commands import set_default_commands


async def _cleanup_loop() -> None:
    """Delete closed support tickets older than 7 days. Runs once a day."""
    while True:
        await asyncio.sleep(24 * 60 * 60)  # 24 hours
        try:
            deleted = delete_old_closed_tickets(days=7)
            if deleted:
                print(f"[support] Удалено {deleted} закрытых тикетов старше 7 дней")
        except Exception as exc:
            print(f"[support] Ошибка очистки тикетов: {exc}")


async def on_startup() -> None:
    await set_default_commands(bot)
    await on_startup_notify(dispatcher)
    print("~~~~~ Бот был запущен ~~~~~")


async def main() -> None:
    create_bdx()
    dispatcher.include_router(router)
    await on_startup()
    asyncio.create_task(_cleanup_loop())
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
