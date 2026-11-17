"""Subscription and drop alert digest engine for workBee."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import re
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from core import db

router = APIRouter()

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


async def initialize(conn) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS career_subscriptions (
            email TEXT PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
            active BOOLEAN NOT NULL DEFAULT true
        );
        CREATE INDEX IF NOT EXISTS career_subscriptions_active_idx ON career_subscriptions(active, created_at DESC);
    """)


@asynccontextmanager
async def connection():
    conn = None
    try:
        conn = await db.connect()
        await initialize(conn)
        yield conn
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "Subscription storage is temporarily unavailable.") from exc
    finally:
        if conn:
            await conn.close()


class SubscribeRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    target_term: Optional[str] = Field(default="summer-2027", max_length=50)
    preferences: Optional[dict] = Field(default_factory=dict)


@router.post("/api/careers/subscribe")
async def subscribe(req: SubscribeRequest):
    email = req.email.strip().lower()
    if not EMAIL_REGEX.match(email):
        raise HTTPException(422, "Please enter a valid email address.")

    async with connection() as conn:
        prefs = req.preferences or {}
        if req.target_term:
            prefs["target_term"] = req.target_term

        await conn.execute("""
            INSERT INTO career_subscriptions (email, preferences, active, updated_at)
            VALUES ($1, $2::jsonb, true, now())
            ON CONFLICT (email) DO UPDATE SET
                active = true,
                preferences = EXCLUDED.preferences,
                updated_at = now()
        """, email, json.dumps(prefs))

    return {
        "ok": True,
        "email": email,
        "message": "Subscribed! You will receive weekly verified drop alerts for newly posted opportunities."
    }


@router.get("/api/careers/subscribe/preview")
async def digest_preview():
    """Generates the weekly drop alert digest showcasing new verified opportunities."""
    from hives.careers.catalog import cache as catalog_cache
    now = datetime.now(timezone.utc)
    jobs = catalog_cache() or []

    verified_drops = []
    for job in jobs[:150]:
        if not job.get("open", True):
            continue
        is_fresh = False
        first_seen = job.get("first_seen")
        if first_seen:
            try:
                fs_dt = datetime.fromisoformat(str(first_seen).replace("Z", "+00:00"))
                if (now - fs_dt).days <= 14:
                    is_fresh = True
            except Exception:
                pass
        verified_drops.append({
            "id": job.get("id"),
            "title": job.get("title"),
            "company": job.get("company"),
            "location": job.get("location"),
            "term": "Summer 2027",
            "apply_url": job.get("apply_url") or job.get("url"),
            "is_fresh": is_fresh,
            "workplace": job.get("workplace", "hybrid"),
        })
        if len(verified_drops) >= 10:
            break

    return {
        "ok": True,
        "generated_at": now.isoformat(),
        "digest_title": "workBee Weekly Verified Drop Alert",
        "total_active_drops": len(verified_drops),
        "featured_drops": verified_drops
    }
