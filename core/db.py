import os

import asyncpg


async def connect():
    return await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://hivework:hivework@localhost:5432/hivework"))


async def initialize() -> None:
    conn = await connect()
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_events (
              id BIGSERIAL PRIMARY KEY,
              hive TEXT NOT NULL,
              bot TEXT NOT NULL,
              kind TEXT NOT NULL,
              detail JSONB NOT NULL DEFAULT '{}'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS bot_events_created_idx ON bot_events (created_at DESC);
        """)
    finally:
        await conn.close()


async def record(hive: str, bot: str, kind: str, detail: dict | None = None) -> None:
    conn = await connect()
    try:
        await conn.execute(
            "INSERT INTO bot_events (hive, bot, kind, detail) VALUES ($1, $2, $3, $4::jsonb)",
            hive, bot, kind, __import__("json").dumps(detail or {}),
        )
    finally:
        await conn.close()
