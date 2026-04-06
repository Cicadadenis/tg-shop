"""Фоновая отмена неоплаченных заказов с предоплатой по таймауту."""

import asyncio

from utils.db_api.shop import expire_stale_prepaid_orders

PREPAID_ORDER_TIMEOUT_MINUTES = 30
_LOOP_INTERVAL_SEC = 60


async def prepaid_order_timeout_loop() -> None:
    """Раз в минуту проверяет заказы «Новый» с предоплатой старше PREPAID_ORDER_TIMEOUT_MINUTES."""
    print(f"[orders] Таймер неоплаты: {PREPAID_ORDER_TIMEOUT_MINUTES} мин, проверка каждые {_LOOP_INTERVAL_SEC} с")
    while True:
        await asyncio.sleep(_LOOP_INTERVAL_SEC)
        try:
            n = expire_stale_prepaid_orders(timeout_minutes=PREPAID_ORDER_TIMEOUT_MINUTES)
            if n:
                print(f"[orders] Переведено в «Удален» (неоплата): {n}")
        except Exception as exc:
            print(f"[orders] Ошибка таймаута оплаты: {exc}")
