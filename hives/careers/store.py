"""Persist complete board snapshots; errors never turn open jobs into closed jobs."""
import json
from datetime import datetime

from core import db
from hives.careers.feeds import employers


async def initialize():
    conn = await db.connect()
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS career_boards (
                key TEXT PRIMARY KEY, company TEXT NOT NULL,
                checked_at TIMESTAMPTZ, attempted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                error TEXT
            );
            CREATE TABLE IF NOT EXISTS career_jobs (
                id TEXT PRIMARY KEY, board_key TEXT NOT NULL, data JSONB NOT NULL,
                first_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
                last_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
                changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                open BOOLEAN NOT NULL DEFAULT true
            );
            ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS verification JSONB;
            CREATE INDEX IF NOT EXISTS career_jobs_board_idx ON career_jobs(board_key);
        """)
    finally:
        await conn.close()


async def save_snapshot(employer, jobs):
    key = f"{employer['source']}:{employer['board']}"
    changes = []
    conn = await db.connect()
    try:
        async with conn.transaction():
            old = {r["id"]: r for r in await conn.fetch("SELECT id, data, open FROM career_jobs WHERE board_key=$1 FOR UPDATE", key)}
            for job in jobs:
                before = old.get(job["id"])
                data = json.dumps(job)
                previous = json.loads(before["data"]) if before and isinstance(before["data"], str) else before["data"] if before else None
                kind = "discovered" if before is None else "reopened" if not before["open"] else "changed" if previous != job else None
                await conn.execute("""
                    INSERT INTO career_jobs(id, board_key, data) VALUES ($1,$2,$3::jsonb)
                    ON CONFLICT(id) DO UPDATE SET data=EXCLUDED.data, open=true, last_seen=now(),
                      changed_at=CASE WHEN career_jobs.data != EXCLUDED.data OR NOT career_jobs.open THEN now() ELSE career_jobs.changed_at END
                """, job["id"], key, data)
                if kind:
                    changes.append({"job_id": job["id"], "kind": kind})
            ids = [j["id"] for j in jobs]
            closed = await conn.fetch("UPDATE career_jobs SET open=false, changed_at=now() WHERE board_key=$1 AND open AND NOT (id=ANY($2::text[])) RETURNING id", key, ids)
            changes.extend({"job_id": r["id"], "kind": "closed"} for r in closed)
            await conn.execute("""INSERT INTO career_boards(key,company,checked_at) VALUES ($1,$2,now())
                ON CONFLICT(key) DO UPDATE SET checked_at=now(), attempted_at=now(), error=NULL""", key, employer["name"])
    finally:
        await conn.close()
    return changes


async def record_error(employer, message):
    conn = await db.connect()
    try:
        await conn.execute("""INSERT INTO career_boards(key,company,error) VALUES ($1,$2,$3)
            ON CONFLICT(key) DO UPDATE SET attempted_at=now(), error=EXCLUDED.error""",
                           f"{employer['source']}:{employer['board']}", employer["name"], message)
    finally:
        await conn.close()


async def catalog(current_only=False,include_community=False):
    conn = await db.connect()
    try:
        keys = [f"{e['source']}:{e['board']}" for e in employers()]
        if current_only:
            # Avoid loading large community/archival descriptions that current search excludes.
            keys=[key for key in keys if key.split(':',1)[0] in ({'greenhouse','lever','ashby','simplify'} if include_community else {'greenhouse','lever','ashby'})]
            rows=await conn.fetch("SELECT * FROM career_jobs WHERE open AND board_key=ANY($1::text[]) AND last_seen >= now()-interval '30 minutes' ORDER BY first_seen DESC",keys)
        else:
            rows = await conn.fetch("SELECT * FROM career_jobs WHERE open AND board_key=ANY($1::text[]) ORDER BY first_seen DESC", keys)
        boards = await conn.fetch("SELECT * FROM career_boards WHERE key=ANY($1::text[]) ORDER BY company", keys)
        jobs = []
        for row in rows:
            data = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
            verification = json.loads(row["verification"]) if isinstance(row["verification"], str) else row["verification"]
            jobs.append({**data, "verification": verification, "first_seen": row["first_seen"].isoformat(), "last_seen": row["last_seen"].isoformat(), "changed_at": row["changed_at"].isoformat()})
        return {"jobs": jobs, "boards": [{**dict(b), "checked_at": b["checked_at"].isoformat() if b["checked_at"] else None, "attempted_at": b["attempted_at"].isoformat()} for b in boards]}
    finally:
        await conn.close()


async def get_job(job_id):
    conn = await db.connect()
    try:
        row = await conn.fetchrow("SELECT data, open, last_seen FROM career_jobs WHERE id=$1", job_id)
        if not row:
            return None
        data = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
        return {**data, "open": row["open"], "last_seen": row["last_seen"].isoformat()}
    finally:
        await conn.close()


async def save_verification(job_id, result):
    conn = await db.connect()
    try:
        await conn.execute("UPDATE career_jobs SET verification=$2::jsonb WHERE id=$1 AND (verification IS NULL OR (verification->>'checked_at')::timestamptz <= $3::timestamptz)", job_id, json.dumps(result), datetime.fromisoformat(result['checked_at']))
    finally:
        await conn.close()
