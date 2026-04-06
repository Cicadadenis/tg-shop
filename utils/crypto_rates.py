"""
Курсы крипты к гривне для счетов CryptoBot.
По умолчанию — CoinGecko (simple/price vs UAH), с коротким кэшем.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import requests

COINGECKO_SIMPLE_PRICE = "https://api.coingecko.com/api/v3/simple/price"
CRYPTOBOT_UAH_PER_UNIT_ENV = "CRYPTOBOT_UAH_PER_CRYPTO_UNIT"
CRYPTOBOT_UAH_PER_UNIT_LEGACY_ENV = "CRYPTOBOT_UAH_PER_USDT"


def _env_uah_fallback() -> float:
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


# CryptoBot asset code -> id CoinGecko
CRYPTOBOT_ASSET_TO_COINGECKO: dict[str, str] = {
    "USDT": "tether",
    "TRX": "tron",
    "LTC": "litecoin",
}

CRYPTOBOT_ALLOWED_ASSETS: tuple[str, ...] = ("USDT", "TRX", "LTC")

_CACHE_TTL_SEC = 90.0
_cache_ts: float = 0.0
_cache_payload: dict[str, Any] | None = None


def _fallback_uah_per_unit(asset: str) -> float:
    """Если API недоступен — запасной курс (env для USDT-подобного или грубые значения)."""
    a = asset.upper()
    if a == "USDT":
        return _env_uah_fallback()
    env_key = f"CRYPTOBOT_FALLBACK_UAH_{a}"
    raw = (os.getenv(env_key) or "").strip()
    if raw:
        try:
            return max(0.01, float(raw.replace(",", ".")))
        except ValueError:
            pass
    # Грубые дефолты, если совсем нет данных (лучше задать CRYPTOBOT_FALLBACK_UAH_TRX и т.д.)
    rough = {"TRX": 8.5, "LTC": 3500.0}
    return rough.get(a, _env_uah_fallback())


def _fetch_coingecko_uah_block(ids_csv: str) -> dict[str, Any]:
    r = requests.get(
        COINGECKO_SIMPLE_PRICE,
        params={"ids": ids_csv, "vs_currencies": "uah", "precision": "full"},
        headers={"Accept": "application/json", "User-Agent": "tg-shop-cryptobot/1.0"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


async def uah_per_unit_for_cryptobot_asset(asset: str) -> tuple[float, str]:
    """
    Сколько гривен за 1 единицу актива (USDT/TRX/LTC).
    Возвращает (курс, метка источника).
    """
    a = (asset or "").strip().upper()
    if a not in CRYPTOBOT_ASSET_TO_COINGECKO:
        return _env_uah_fallback(), "env (неизвестный актив)"

    global _cache_ts, _cache_payload
    now = time.monotonic()
    if _cache_payload is None or (now - _cache_ts) > _CACHE_TTL_SEC:
        ids_csv = ",".join(sorted(set(CRYPTOBOT_ASSET_TO_COINGECKO.values())))
        try:
            _cache_payload = await asyncio.to_thread(_fetch_coingecko_uah_block, ids_csv)
        except Exception:
            if _cache_payload is None:
                _cache_payload = {}
        _cache_ts = now

    cg_id = CRYPTOBOT_ASSET_TO_COINGECKO[a]
    if isinstance(_cache_payload, dict) and cg_id in _cache_payload:
        uah = (_cache_payload[cg_id] or {}).get("uah")
        if uah is not None:
            try:
                v = float(uah)
                if v > 0:
                    return v, "CoinGecko (UAH)"
            except (TypeError, ValueError):
                pass

    return _fallback_uah_per_unit(a), "запасной курс"
