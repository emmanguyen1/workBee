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
            ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS summary JSONB;
            ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS search_document TEXT;
            ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS summary_changed_at TIMESTAMPTZ;
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
                from hives.careers.search_index import build
                summary,document=build(job,employer)
                writes.append((job["id"],key,data,json.dumps(summary),document))
                if kind:
                    changes.append({"job_id": job["id"], "kind": kind})
            if writes:
                await conn.executemany("""
                    INSERT INTO career_jobs(id, board_key, data, summary, search_document,summary_changed_at) VALUES ($1,$2,$3::jsonb,$4::jsonb,$5,now())
                    ON CONFLICT(id) DO UPDATE SET data=EXCLUDED.data,summary=EXCLUDED.summary,search_document=EXCLUDED.search_document,summary_changed_at=now(), open=true, last_seen=now(),
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


async def catalog_revision(current_only=False,include_community=False,include_stale=False,compact=False):
    conn=await db.connect()
    try:
        keys=catalog_keys(current_only,include_community)
        async with conn.transaction(isolation='repeatable_read',readonly=True):
            boards=await conn.fetch('SELECT * FROM career_boards WHERE key=ANY($1::text[])',keys)
            verified=await conn.fetchval("SELECT max(verification->>'checked_at') FROM career_jobs WHERE open AND board_key=ANY($1::text[])"+catalog_window(current_only,include_stale),keys)
        return fingerprint(boards,verified)
    finally:await conn.close()


async def catalog(current_only=False,include_community=False,include_stale=False,compact=False):
    conn=await db.connect()
    try:
        keys=catalog_keys(current_only,include_community)
        if compact:
            # Compatibility for an existing database before the one-time index upgrade.
            ready=await conn.fetchval("SELECT EXISTS(SELECT 1 FROM pg_attribute WHERE attrelid='career_jobs'::regclass AND attname='summary_changed_at' AND NOT attisdropped)")
            if not ready:await conn.execute('ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS summary JSONB; ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS search_document TEXT; ALTER TABLE career_jobs ADD COLUMN IF NOT EXISTS summary_changed_at TIMESTAMPTZ')
        # Rows and source metadata describe the same database snapshot.
        async with conn.transaction(isolation='repeatable_read',readonly=True):
            if compact:
                from hives.careers.search_index import VERSION,REQUIREMENTS_VERSION,QUALIFICATION_VERSION
                rows=await conn.fetch("SELECT id,first_seen,last_seen,changed_at,verification,CASE WHEN summary_changed_at>=changed_at AND summary->>'summary_version'=$2 AND summary->>'requirements_version'=$3 AND summary->>'qualification_version'=$4 THEN summary ELSE data END AS data FROM career_jobs WHERE open AND board_key=ANY($1::text[])"+catalog_window(current_only,include_stale)+" ORDER BY first_seen DESC,id",keys,str(VERSION),str(REQUIREMENTS_VERSION),str(QUALIFICATION_VERSION))
            else:
                rows=await conn.fetch("SELECT id,data,first_seen,last_seen,changed_at,verification FROM career_jobs WHERE open AND board_key=ANY($1::text[])"+catalog_window(current_only,include_stale)+" ORDER BY first_seen DESC,id",keys)
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
        row = await conn.fetchrow("SELECT data, open, last_seen,first_seen,changed_at,verification FROM career_jobs WHERE id=$1", job_id)
        if not row:
            return None
        data = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
        verification=json.loads(row['verification']) if isinstance(row['verification'],str) else row['verification']
        return {**data,"verification":verification,"open":row["open"],"last_seen":row["last_seen"].isoformat(),"first_seen":row["first_seen"].isoformat(),"changed_at":row["changed_at"].isoformat()}
    finally:
        await conn.close()


async def save_verification(job_id, result):
    conn = await db.connect()
    try:
        await conn.execute("UPDATE career_jobs SET verification=$2::jsonb WHERE id=$1 AND (verification IS NULL OR (verification->>'checked_at')::timestamptz <= $3::timestamptz)", job_id, json.dumps(result), datetime.fromisoformat(result['checked_at']))
        invalidate_catalog()
    finally:
        await conn.close()


async def query_ids(query,current_only=False,include_community=False,include_stale=False,compact=False):
    conn=await db.connect()
    try:
        words=[w.replace('\\','\\\\').replace('%','\\%').replace('_','\\_') for w in query.casefold().split()]
        rows=await conn.fetch("SELECT id FROM career_jobs WHERE open AND board_key=ANY($1::text[])"+catalog_window(current_only,include_stale)+" AND NOT EXISTS (SELECT 1 FROM unnest($2::text[]) AS term WHERE COALESCE(CASE WHEN summary_changed_at>=changed_at THEN search_document END,lower(coalesce(data->>'title','') || ' ' || coalesce(data->>'company','') || ' ' || coalesce(data->>'locations',data->>'location','') || ' ' || coalesce(data->>'description','') || ' ' || coalesce(data->>'search_text',''))) NOT LIKE '%' || term || '%')",catalog_keys(current_only,include_community),words)
        return {row['id'] for row in rows}
    finally:await conn.close()


async def get_board(job):
    conn=await db.connect()
    try:
        row=await conn.fetchrow('SELECT * FROM career_boards WHERE key=$1',f"{job.get('source')}:{job.get('board')}")
        return dict(row) if row else None
    finally:await conn.close()
