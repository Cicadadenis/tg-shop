# - *- coding: utf- 8 - *-
import asyncio

from handlers import router
from loader import bot, dispatcher
from utils.db_api.sqlite import create_bdx
from utils.cart_reminders import cart_abandon_reminder_loop
from utils.cryptobot_payments import cryptobot_invoice_watcher_loop
from utils.db_api.shop import delete_old_closed_tickets
from utils.order_payment_timeout import prepaid_order_timeout_loop
from utils.other_func import on_startup_notify
from utils.bot_restart import consume_restart_request, perform_execl_restart
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
    asyncio.create_task(cart_abandon_reminder_loop(bot))
    asyncio.create_task(cryptobot_invoice_watcher_loop(bot))
    asyncio.create_task(prepaid_order_timeout_loop())
    try:
        await dispatcher.start_polling(bot)
    finally:
        need_restart = consume_restart_request()
        try:
            await bot.session.close()
        except Exception:
            pass
        if need_restart:
            perform_execl_restart()


if __name__ == "__main__":
    asyncio.run(main())
