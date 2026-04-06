import asyncio
import json
import os
from typing import Any

import requests
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

try:
    from cryptopay import CryptoPay  # type: ignore
except Exception:
    CryptoPay = None

from keyboards.inline.shop_inline import admin_order_status_kb
from utils.crypto_rates import uah_per_unit_for_cryptobot_asset
from utils.db_api.shop import (
    get_cryptobot_token,
    get_admin_ids,
    get_notify_chat_id,
    get_order,
    get_order_items,
    list_pending_crypto_invoices,
    mark_crypto_invoice_paid,
    upsert_crypto_invoice,
    update_order_status,
)

CRYPTOBOT_API_BASE = "https://pay.crypt.bot/api"
CRYPTOBOT_ASSET_ENV = "CRYPTOBOT_ASSET"
CRYPTOBOT_ASSET_DEFAULT = "USDT"
CRYPTOBOT_POLL_INTERVAL_ENV = "CRYPTOBOT_POLL_INTERVAL"
# Сумма заказа в боте в гривнах; в CryptoBot счёт выставляется в единицах актива (USDT и т.д.).
# Сколько гривен за 1 единицу актива (например 42 = 1 USDT ≈ 42 грн). Подстройте под рынок.
CRYPTOBOT_UAH_PER_UNIT_ENV = "CRYPTOBOT_UAH_PER_CRYPTO_UNIT"
CRYPTOBOT_UAH_PER_UNIT_LEGACY_ENV = "CRYPTOBOT_UAH_PER_USDT"


def _token() -> str:
    tok = get_cryptobot_token()
    if tok:
        return tok
    # fallback for legacy deployments
    return (os.getenv("CRYPTOBOT_TOKEN") or "").strip()


def _asset() -> str:
    value = (os.getenv(CRYPTOBOT_ASSET_ENV) or CRYPTOBOT_ASSET_DEFAULT).strip().upper()
    return value or CRYPTOBOT_ASSET_DEFAULT


def _poll_interval() -> int:
    raw = (os.getenv(CRYPTOBOT_POLL_INTERVAL_ENV) or "20").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 20
    return max(10, min(300, value))


def uah_per_cryptobot_unit() -> float:
    raw = (
        os.getenv(CRYPTOBOT_UAH_PER_UNIT_ENV)
        or os.getenv(CRYPTOBOT_UAH_PER_UNIT_LEGACY_ENV)
        or "42"
    )
    try:
        v = float(str(raw).replace(",", ".").strip())
    except ValueError:
        v = 42.0
    return max(0.01, v)


def _crypto_amount_str_from_uah(uah_total: int, asset: str, uah_per_unit: float) -> str:
    uah = max(1, int(uah_total))
    amount = uah / max(0.01, float(uah_per_unit))
    a = (asset or "").strip().upper()
    if a in ("USDT", "USDC"):
        q = round(amount, 2)
        return f"{q:.2f}"
    if a in ("TRX", "TON"):
        q = round(amount, 4)
        return f"{q:.4f}"
    if a in ("LTC", "BTC", "ETH"):
        q = round(amount, 8)
        return f"{q:.8f}"
    q = round(amount, 6)
    return f"{q:.6f}"


def cryptobot_enabled() -> bool:
    return bool(_token())


def _headers() -> dict[str, str]:
    return {
        "Crypto-Pay-API-Token": _token(),
        "Content-Type": "application/json",
    }


def _client():
    if not CryptoPay:
        return None
    tok = _token()
    if not tok:
        return None
    try:
        return CryptoPay(token=tok)
    except Exception:
        return None


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(url, headers=_headers(), json=payload, timeout=20)
    response.raise_for_status()
    return response.json()


def _extract_invoice_payload(raw: dict[str, Any]) -> tuple[int, str, str]:
    if not raw.get("ok"):
        err = str(raw.get("error") or "Ошибка API CryptoBot")
        raise RuntimeError(err)

    result = raw.get("result") or {}
    inv_id = int(result.get("invoice_id") or 0)
    pay_url = str(result.get("pay_url") or "").strip()
    status = str(result.get("status") or "").strip().lower()
    if inv_id <= 0 or not pay_url:
        raise RuntimeError("CryptoBot вернул пустой invoice_id/pay_url")
    return inv_id, pay_url, status


async def create_cryptobot_invoice_for_order(
    *,
    order_id: str,
    user_id: int,
    total_amount: int,
    description: str,
    asset: str | None = None,
) -> tuple[bool, str, str, str, float, str]:
    """
    total_amount — сумма заказа в гривнах.
    asset — USDT / TRX / LTC (или из CRYPTOBOT_ASSET по умолчанию).
    Возвращает (ok, pay_url_or_error, asset, amount_in_asset_str, uah_per_unit, rate_source).
    """
    token = _token()
    if not token:
        return False, "CRYPTOBOT_TOKEN не задан", "", "", 0.0, ""

    uah_total = max(1, int(total_amount))
    asset = ((asset or _asset()) or CRYPTOBOT_ASSET_DEFAULT).strip().upper()
    uah_rate, rate_src = await uah_per_unit_for_cryptobot_asset(asset)
    amount_str = _crypto_amount_str_from_uah(uah_total, asset, uah_rate)

    payload = {
        "asset": asset,
        "amount": amount_str,
        "description": description[:1024],
        "hidden_message": f"Спасибо за оплату заказа {order_id}",
    }

    client = _client()
    try:
        if client:
            inv_obj = await client.create_invoice(
                asset=asset,
                amount=amount_str,
                description=description[:1024],
            )
            invoice_id = int(getattr(inv_obj, "invoice_id", 0) or 0)
            pay_url = str(getattr(inv_obj, "pay_url", "") or "").strip()
            if invoice_id <= 0 or not pay_url:
                raise RuntimeError("crypto-pay-api вернул пустой invoice_id/pay_url")
        else:
            raw = await asyncio.to_thread(_post_json, f"{CRYPTOBOT_API_BASE}/createInvoice", payload)
            invoice_id, pay_url, _ = _extract_invoice_payload(raw)
    except Exception as exc:
        return False, str(exc), asset, "", 0.0, rate_src

    upsert_crypto_invoice(
        order_id=order_id,
        user_id=int(user_id),
        invoice_id=invoice_id,
        asset=asset,
        amount=amount_str,
        pay_url=pay_url,
    )
    return True, pay_url, asset, amount_str, uah_rate, rate_src


async def _fetch_invoice_status(invoice_id: int) -> tuple[bool, str, str]:
    """
    Возвращает (ok, status_or_error, raw_payload_json).
    """
    payload = {"invoice_ids": str(int(invoice_id))}
    client = _client()

    if client:
        try:
            invoices = await client.get_invoices(invoice_ids=str(int(invoice_id)))
            first = None
            if isinstance(invoices, list) and invoices:
                first = invoices[0]
            elif hasattr(invoices, "items"):
                items = getattr(invoices, "items", [])
                if items:
                    first = items[0]
            if not first:
                return False, "Инвойс не найден", ""
            status = str(getattr(first, "status", "") or "").strip().lower()
            return True, status, ""
        except Exception:
            # fallback ниже
            pass

    try:
        raw = await asyncio.to_thread(_post_json, f"{CRYPTOBOT_API_BASE}/getInvoices", payload)
    except Exception as exc:
        return False, str(exc), ""

    if not raw.get("ok"):
        return False, str(raw.get("error") or "Ошибка API CryptoBot"), json.dumps(raw, ensure_ascii=False)

    result = raw.get("result") or {}
    items = result.get("items") or []
    if not items:
        return False, "Инвойс не найден", json.dumps(raw, ensure_ascii=False)

    status = str(items[0].get("status") or "").strip().lower()
    return True, status, json.dumps(raw, ensure_ascii=False)


def _admin_order_text(order_id: str, order: dict[str, Any], items: list[dict[str, Any]]) -> str:
    lines = [f"• {i['title']} — {i['quantity']} x {i['price']} грн" for i in items]
    promo = f"🏷 Промокод: <b>{order['promo_code']}</b>\n" if order.get("promo_code") else ""
    return (
        f"<b>📦 Заказ {order_id}</b>\n"
        f"📌 Статус: <b>{order['status']}</b>\n"
        f"👤 Клиент: <b>{order['name']}</b>\n"
        f"📞 Телефон: <b>{order['phone']}</b>\n"
        f"📍 Адрес: <b>{order['address']}</b>\n"
        f"🚚 Доставка: <b>{order['delivery']}</b>\n"
        f"💳 Оплата: <b>{order['payment']}</b>\n"
        f"🧾 Чек: <b>подтвержден автоматически (CryptoBot)</b>\n"
        f"{promo}"
        f"💰 Итого: <b>{order['total']} грн</b>\n\n"
        f"{chr(10).join(lines)}"
    )


async def _notify_paid_order(bot: Bot, order_id: str) -> None:
    order = get_order(order_id)
    if not order:
        return
    items = get_order_items(order_id)
    text = _admin_order_text(order_id, order, items)

    kb = admin_order_status_kb(
        order_id,
        order["user_id"],
        receipt_pending=False,
        has_receipt=bool(order.get("receipt_sent", False)),
        current_status_raw=order.get("status_raw", ""),
        payment_label=order.get("payment", ""),
    )

    for admin_id in get_admin_ids():
        try:
            await bot.send_message(int(admin_id), text, reply_markup=kb)
        except Exception:
            pass

    notify_chat_id = get_notify_chat_id()
    if notify_chat_id:
        try:
            await bot.send_message(int(notify_chat_id), text, reply_markup=kb)
        except Exception:
            pass

    try:
        user_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📦 Открыть заказ", callback_data=f"shop:order:{order_id}")],
                [InlineKeyboardButton(text="⬅ К заказам", callback_data="menu:orders")],
            ]
        )
        await bot.send_message(
            int(order["user_id"]),
            f"✅ Оплата заказа <code>{order_id}</code> подтверждена через CryptoBot.",
            reply_markup=user_kb,
        )
    except Exception:
        pass


async def cryptobot_invoice_watcher_loop(bot: Bot) -> None:
    if not cryptobot_enabled():
        print("[cryptobot] CRYPTOBOT_TOKEN не задан, авто-проверка инвойсов отключена")
        return

    print("[cryptobot] Запущен мониторинг инвойсов")
    while True:
        await asyncio.sleep(_poll_interval())
        pending = list_pending_crypto_invoices(limit=100)
        if not pending:
            continue

        for inv in pending:
            order_id = str(inv.get("order_id") or "").strip()
            invoice_id = int(inv.get("invoice_id") or 0)
            if not order_id or invoice_id <= 0:
                continue

            order_row = get_order(order_id)
            if not order_row or str(order_row.get("status_raw") or "").strip() != "Новый":
                continue

            ok, status_or_error, raw_payload = await _fetch_invoice_status(invoice_id)
            if not ok:
                continue

            if status_or_error != "paid":
                continue

            changed = mark_crypto_invoice_paid(invoice_id, raw_payload=raw_payload)
            if not changed:
                continue

            update_order_status(order_id, "paid")
            await _notify_paid_order(bot, order_id)
