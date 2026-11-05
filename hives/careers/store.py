"""Persist complete board snapshots; errors never turn open jobs into closed jobs."""
import json
import hashlib
import asyncio
from datetime import datetime

from core import db
from hives.careers.feeds import employers

_EPOCH=0

def catalog_epoch():return _EPOCH

def invalidate_catalog():
    global _EPOCH
    _EPOCH+=1



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
            CREATE INDEX IF NOT EXISTS career_jobs_current_idx ON career_jobs(last_seen,board_key) WHERE open;
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
            writes=[]
            for job in jobs:
                before = old.get(job["id"])
                data = json.dumps(job)
                previous = json.loads(before["data"]) if before and isinstance(before["data"], str) else before["data"] if before else None
                kind = "discovered" if before is None else "reopened" if not before["open"] else "changed" if previous != job else None
                writes.append((job["id"], key, data))
                if kind:
                    changes.append({"job_id": job["id"], "kind": kind})
            if writes:
                await conn.executemany("""
                    INSERT INTO career_jobs(id, board_key, data) VALUES ($1,$2,$3::jsonb)
                    ON CONFLICT(id) DO UPDATE SET data=EXCLUDED.data, open=true, last_seen=now(),
                      changed_at=CASE WHEN career_jobs.data != EXCLUDED.data OR NOT career_jobs.open THEN now() ELSE career_jobs.changed_at END
                """, writes)
            ids = [j["id"] for j in jobs]
            closed = await conn.fetch("UPDATE career_jobs SET open=false, changed_at=now() WHERE board_key=$1 AND open AND NOT (id=ANY($2::text[])) RETURNING id", key, ids)
            changes.extend({"job_id": r["id"], "kind": "closed"} for r in closed)
            await conn.execute("""INSERT INTO career_boards(key,company,checked_at) VALUES ($1,$2,now())
                ON CONFLICT(key) DO UPDATE SET checked_at=now(), attempted_at=now(), error=NULL""", key, employer["name"])
    finally:
        await conn.close()
    invalidate_catalog()
    return changes


async def record_error(employer, message):
    conn = await db.connect()
    try:
        await conn.execute("""INSERT INTO career_boards(key,company,error) VALUES ($1,$2,$3)
            ON CONFLICT(key) DO UPDATE SET attempted_at=now(), error=EXCLUDED.error""",
                           f"{employer['source']}:{employer['board']}", employer["name"], message)
        invalidate_catalog()
    finally:
        await conn.close()


def catalog_keys(current_only=False,include_community=False):
    return [f"{e['source']}:{e['board']}" for e in employers() if not current_only or e['source'] in ({'greenhouse','lever','ashby','simplify'} if include_community else {'greenhouse','lever','ashby'})]


def fingerprint(boards,verified):
    metadata=[(b['key'],b['checked_at'],b['attempted_at'],b['error']) for b in sorted(boards,key=lambda b:b['key'])]
    return hashlib.sha256(json.dumps([metadata,verified],default=str).encode()).hexdigest()


def catalog_window(current_only,include_stale):
    return (" AND last_seen >= now()-interval '7 days'" if include_stale else " AND last_seen >= now()-interval '30 minutes'") if current_only else ''


async def catalog_revision(current_only=False,include_community=False,include_stale=False):
    conn=await db.connect()
    try:
        keys=catalog_keys(current_only,include_community)
        async with conn.transaction(isolation='repeatable_read',readonly=True):
            boards=await conn.fetch('SELECT * FROM career_boards WHERE key=ANY($1::text[])',keys)
            verified=await conn.fetchval("SELECT max(verification->>'checked_at') FROM career_jobs WHERE open AND board_key=ANY($1::text[])"+catalog_window(current_only,include_stale),keys)
        return fingerprint(boards,verified)
    finally:await conn.close()


async def catalog(current_only=False,include_community=False,include_stale=False):
    conn=await db.connect()
    try:
        keys=catalog_keys(current_only,include_community)
        # Rows and source metadata describe the same database snapshot.
        async with conn.transaction(isolation='repeatable_read',readonly=True):
            rows=await conn.fetch("SELECT * FROM career_jobs WHERE open AND board_key=ANY($1::text[])"+catalog_window(current_only,include_stale)+" ORDER BY first_seen DESC",keys)
            boards=await conn.fetch('SELECT * FROM career_boards WHERE key=ANY($1::text[]) ORDER BY company',keys)
        def decoded():
            jobs=[];verified=[]
            for row in rows:
                data=json.loads(row['data']) if isinstance(row['data'],str) else row['data']
                verification=json.loads(row['verification']) if isinstance(row['verification'],str) else row['verification']
                if verification and verification.get('checked_at'):verified.append(verification['checked_at'])
                jobs.append({**data,'verification':verification,'first_seen':row['first_seen'].isoformat(),'last_seen':row['last_seen'].isoformat(),'changed_at':row['changed_at'].isoformat()})
            return {'jobs':jobs,'revision':fingerprint(boards,max(verified) if verified else None),'boards':[{**dict(b),'checked_at':b['checked_at'].isoformat() if b['checked_at'] else None,'attempted_at':b['attempted_at'].isoformat()} for b in boards]}
        return await asyncio.to_thread(decoded)
    finally:await conn.close()


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
        invalidate_catalog()
    finally:
        await conn.close()
