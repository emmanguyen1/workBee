"""Read-only, token-protected HTTP bridge from Vercel to local Redis."""

import hmac
import os

from fastapi import FastAPI, Header, HTTPException

from core import bus

app = FastAPI(title="Hivework Redis bridge", docs_url=None, redoc_url=None)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/topics/{hive}/{topic}")
async def topic(
    hive: str,
    topic: str,
    count: int = 30,
    authorization: str | None = Header(default=None),
):
    expected = os.getenv("REDIS_BRIDGE_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="Bridge token is not configured")
    supplied = authorization.removeprefix("Bearer ") if authorization else ""
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if (hive, topic) != ("kalshi", "status"):
        raise HTTPException(status_code=404, detail="Topic not available")
    if not 1 <= count <= 100:
        raise HTTPException(status_code=400, detail="count must be between 1 and 100")
    try:
        events = await bus.latest(f"{hive}:{topic}", count)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Redis is unavailable") from exc
    return {"hive": hive, "topic": topic, "events": events}
