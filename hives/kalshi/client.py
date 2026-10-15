"""Read-only Kalshi demo portfolio client. No production or trading methods."""

import asyncio
import base64
import os
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding

BASE_URL = "https://demo-api.kalshi.co"
_cache = None
_cached_at = 0.0
_lock = asyncio.Lock()
_retry_at = 0.0


class DemoUnavailable(Exception):
    pass


def open_position_returns(positions, value_cents):
    """Compare Kalshi's current portfolio valuation to remaining position cost."""
    def total(field):
        try:
            return sum((Decimal(str(p[field])) for p in positions), Decimal(0)) * 100
        except (KeyError, InvalidOperation, TypeError):
            return None

    cost = total("market_exposure_dollars")
    fees = total("fees_paid_dollars")
    unrealized = Decimal(str(value_cents)) - cost if cost is not None else None
    return {
        "open_cost_cents": float(cost) if cost is not None else None,
        "unrealized_pnl_cents": float(unrealized) if unrealized is not None else None,
        "unrealized_return_percent": float(unrealized / cost * 100) if cost and unrealized is not None else None,
        "open_market_fees_cents": float(fees) if fees is not None else None,
    }


async def portfolio():
    global _cache, _cached_at, _retry_at
    async with _lock:
        if _cache is not None and time.monotonic() - _cached_at < 10:
            return _cache
        if time.monotonic() < _retry_at:
            raise DemoUnavailable("Kalshi demo is rate limiting requests. Retrying shortly.")
        key_id = os.getenv("KALSHI_API_KEY_ID", "")
        pem = os.getenv("KALSHI_PRIVATE_KEY", "").replace("\\n", "\n")
        if not key_id or not pem:
            raise DemoUnavailable("Kalshi demo credentials are not configured.")
        try:
            key = serialization.load_pem_private_key(pem.encode(), password=None)
        except (ValueError, TypeError) as exc:
            raise DemoUnavailable("Kalshi demo private key is invalid.") from exc

        async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as client:
            async def get(endpoint, params=None):
                global _retry_at
                path = "/trade-api/v2" + endpoint
                stamp = str(int(time.time() * 1000))
                message = (stamp + "GET" + path).encode()
                if isinstance(key, ed25519.Ed25519PrivateKey):
                    signature = key.sign(message)
                else:
                    signature = key.sign(message, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32), hashes.SHA256())
                response = await client.get(path, params=params, headers={
                    "KALSHI-ACCESS-KEY": key_id,
                    "KALSHI-ACCESS-TIMESTAMP": stamp,
                    "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
                })
                if response.status_code == 429:
                    _retry_at = time.monotonic() + 60
                    raise DemoUnavailable("Kalshi demo is rate limiting requests. Retrying shortly.")
                if response.status_code in (401, 403):
                    raise DemoUnavailable("Kalshi rejected the demo credentials. Check the demo API key and private key.")
                response.raise_for_status()
                return response.json()

            async def pages(endpoint, field, params=None):
                items, cursor = [], None
                for _ in range(20):
                    query = {"limit": 100, **(params or {})}
                    if cursor:
                        query["cursor"] = cursor
                    data = await get(endpoint, query)
                    items.extend(data.get(field, []))
                    cursor = data.get("cursor")
                    if not cursor:
                        return items
                raise DemoUnavailable("Demo portfolio is too large to load completely.")

            try:
                balance = await get("/portfolio/balance")
                positions = await pages("/portfolio/positions", "market_positions", {"count_filter": "position"})
                orders = await pages("/portfolio/orders", "orders", {"status": "resting"})
                fills = await get("/portfolio/fills", {"limit": 50})
            except httpx.HTTPError as exc:
                raise DemoUnavailable("Could not reach Kalshi demo. Retrying automatically.") from exc
        def display_fields(items):
            allowed = {
                "ticker", "market_ticker", "position_fp", "position",
                "action", "side", "remaining_count_fp", "remaining_count",
                "count_fp", "count", "created_time", "status",
                "market_exposure_dollars", "fees_paid_dollars",
            }
            return [{name: value for name, value in item.items() if name in allowed} for item in items]

        _cache = {
            "environment": "demo", "read_only": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "cash_cents": balance["balance"],
            "positions_value_cents": balance["portfolio_value"],
            **open_position_returns(positions, balance["portfolio_value"]),
            "positions": display_fields(positions), "orders": display_fields(orders),
            "fills": display_fields(fills.get("fills", [])), "history_limit": 50,
        }
        _cached_at = time.monotonic()
        return _cache
