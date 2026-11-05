"""Finite, explicit source refreshes. No queue worker, Redis, scheduler or idle polling."""
import asyncio
import json
from datetime import datetime,timezone
from threading import Event
from uuid import uuid4

import httpx
from fastapi import APIRouter,HTTPException,Request,Response
from pydantic import BaseModel,Field,model_validator
from core import db
from hives.careers import store
from hives.careers.accounts import same_origin
from hives.careers.feeds import employers,fetch_board

router=APIRouter(prefix='/api/careers/refresh')
LOCK_KEY=187263901
_TASKS={}
PRIVATE={'Cache-Control':'no-store'}

def stamp():return datetime.now(timezone.utc).isoformat()
def decode(value):return json.loads(value) if isinstance(value,str) else value

def limited_sources(data):
    configured=employers();known={f"{e['source']}:{e['board']}":e for e in configured}
    if data.boards:
        if any(key not in known for key in data.boards):raise HTTPException(400,'Unknown source.',headers=PRIVATE)
        return [e for key,e in known.items() if key in data.boards]
    if data.companies and not set(data.companies).issubset({e['name'] for e in configured}):
        raise HTTPException(400,'Unknown employer.',headers=PRIVATE)
    return [e for e in configured if (e['source']!='simplify' or data.include_community) and (not data.companies or e['name'] in data.companies)]

class RefreshRequest(BaseModel):
    companies:list[str]=Field(default_factory=list,max_length=100)
    boards:list[str]=Field(default_factory=list,max_length=100)
    include_community:bool=False
    @model_validator(mode='after')
    def one_scope(self):
        if self.companies and self.boards:raise ValueError('Choose employers or sources, not both.')
        return self

async def initialize(conn):
    await conn.execute('''CREATE TABLE IF NOT EXISTS career_refreshes (
      id TEXT PRIMARY KEY, state JSONB NOT NULL, cancel_requested BOOLEAN NOT NULL DEFAULT false,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(), finished_at TIMESTAMPTZ
    )''')

async def latest(conn):
    row=await conn.fetchrow('SELECT id,state,cancel_requested FROM career_refreshes ORDER BY created_at DESC LIMIT 1')
    if not row:return None
    state=decode(row['state']);state['cancel_requested']=row['cancel_requested']
    if state['status']=='running' and await conn.fetchval('SELECT pg_try_advisory_lock($1::bigint)',LOCK_KEY):
        try:
            state.update(status='interrupted',finished_at=stamp(),message='Refresh was interrupted. Finished source snapshots remain saved; start another check when ready.')
            await conn.execute('UPDATE career_refreshes SET state=$2::jsonb,finished_at=now() WHERE id=$1',row['id'],json.dumps(state))
        finally:await conn.execute('SELECT pg_advisory_unlock($1::bigint)',LOCK_KEY)
    return state

async def source_status(conn):
    rows=await conn.fetch('SELECT * FROM career_boards') if await conn.fetchval("SELECT to_regclass('career_boards')") else []
    stored={row['key']:row for row in rows}
    result=[]
    for employer in employers():
        key=f"{employer['source']}:{employer['board']}";row=stored.get(key)
        result.append({'key':key,'company':employer['name'],'source':employer['source'],
          'checked_at':row['checked_at'].isoformat() if row and row['checked_at'] else None,
          'attempted_at':row['attempted_at'].isoformat() if row and row['attempted_at'] else None,
          'error':row['error'] if row else None})
    return result

async def checkpoint(conn,state,finished=False):
    state['completed']=sum(s['status'] not in {'pending','running'} for s in state['sources'])
    await conn.execute('UPDATE career_refreshes SET state=$2::jsonb,finished_at=CASE WHEN $3 THEN now() ELSE finished_at END WHERE id=$1',state['id'],json.dumps(state),finished)

async def run(conn,state,selected,event):
    try:
        await store.initialize()
        old={row['key']:row for row in await conn.fetch('SELECT * FROM career_boards')}
        async with httpx.AsyncClient(timeout=30,headers={'User-Agent':'workBee-Manual-Refresh/1.0'}) as client:
            for employer,item in zip(selected,state['sources']):
                if event.is_set() or await conn.fetchval('SELECT cancel_requested FROM career_refreshes WHERE id=$1',state['id']):raise asyncio.CancelledError()
                before=old.get(item['key']);now=datetime.now(timezone.utc)
                recent=before['attempted_at'] if before and before['error'] else before['checked_at'] if before else None
                cooldown=60 if before and before['error'] else 300
                if recent and (now-recent).total_seconds()<cooldown:
                    item.update(status='skipped',message='Source checked recently; no new network request.',checked_at=before['checked_at'].isoformat() if before['checked_at'] else None)
                    await checkpoint(conn,state);continue
                item.update(status='running',started_at=stamp());await checkpoint(conn,state)
                try:
                    jobs=await fetch_board(client,employer,cancel_event=event)
                    if event.is_set() or await conn.fetchval('SELECT cancel_requested FROM career_refreshes WHERE id=$1',state['id']):raise asyncio.CancelledError()
                    changes=await store.save_snapshot(employer,jobs)
                    item.update(status='refreshed',checked_at=stamp(),jobs=len(jobs),changes=len(changes),message='Complete source snapshot saved.')
                except (httpx.HTTPError,ValueError,KeyError,TypeError):
                    message='Source unavailable; last successful snapshot preserved.'
                    await store.record_error(employer,message)
                    item.update(status='error',message=message)
                await checkpoint(conn,state)
        state.update(status='completed',finished_at=stamp(),message='Refresh complete. Review any source errors below.')
    except asyncio.CancelledError:
        event.set()
        for item in state['sources']:
            if item['status'] in {'pending','running'}:item.update(status='cancelled',message='Not refreshed; previous snapshot preserved.')
        state.update(status='cancelled',finished_at=stamp(),message='Refresh cancelled. Completed snapshots remain saved.')
    except Exception:
        event.set()
        for item in state['sources']:
            if item['status'] in {'pending','running'}:item.update(status='error',message='Refresh interrupted; previous snapshot preserved.')
        state.update(status='failed',finished_at=stamp(),message='Refresh could not finish. Completed snapshots remain saved.')
    finally:
        try:await checkpoint(conn,state,finished=True)
        finally:
            try:await conn.execute('SELECT pg_advisory_unlock($1::bigint)',LOCK_KEY)
            finally:await conn.close()
        _TASKS.pop(state['id'],None)

async def shutdown():
    active=list(_TASKS.values())
    for task,event in active:event.set();task.cancel()
    if active:await asyncio.gather(*(task for task,event in active),return_exceptions=True)

@router.get('')
async def status(response:Response):
    response.headers.update(PRIVATE);conn=None
    try:
        conn=await db.connect();await initialize(conn)
        return {'refresh':await latest(conn),'sources':await source_status(conn)}
    except Exception as exc:raise HTTPException(503,'Source status is unavailable. Retry shortly.',headers=PRIVATE) from exc
    finally:
        if conn:await conn.close()

@router.post('',status_code=202)
async def start(data:RefreshRequest,request:Request,response:Response):
    same_origin(request);response.headers.update(PRIVATE)
    selected=limited_sources(data)
    if not selected:raise HTTPException(400,'No configured sources match this refresh.',headers=PRIVATE)
    conn=None;locked=False;handed_off=False
    try:
        conn=await db.connect();await initialize(conn)
        locked=await conn.fetchval('SELECT pg_try_advisory_lock($1::bigint)',LOCK_KEY)
        if not locked:
            current=await latest(conn)
            if current and current['status']=='running':return {'refresh':current,'joined':True}
            raise HTTPException(409,'A refresh is starting. Retry shortly.',headers=PRIVATE)
        # Finalize any abandoned record before starting this finite job.
        await conn.execute("UPDATE career_refreshes SET state=jsonb_set(state,'{status}','\"interrupted\"'::jsonb),finished_at=now() WHERE finished_at IS NULL")
        state={'id':uuid4().hex,'status':'running','started_at':stamp(),'finished_at':None,'completed':0,'total':len(selected),'message':'Checking sources on demand.','sources':[{'key':f"{e['source']}:{e['board']}",'company':e['name'],'status':'pending'} for e in selected]}
        await conn.execute('INSERT INTO career_refreshes(id,state) VALUES ($1,$2::jsonb)',state['id'],json.dumps(state))
        await conn.execute("DELETE FROM career_refreshes WHERE finished_at<now()-interval '7 days'")
        event=Event();task=asyncio.create_task(run(conn,state,selected,event));_TASKS[state['id']]=(task,event)
        def finished(task):
            _TASKS.pop(state['id'],None)
            if not task.cancelled():task.exception()
        task.add_done_callback(finished);handed_off=True
        await asyncio.sleep(0)  # Enter the job's cleanup scope before exposing its ID.
        return {'refresh':state,'joined':False}
    except HTTPException:raise
    except Exception as exc:raise HTTPException(503,'Refresh could not start. Retry shortly.',headers=PRIVATE) from exc
    finally:
        if conn and not handed_off:
            if locked:await conn.execute('SELECT pg_advisory_unlock($1::bigint)',LOCK_KEY)
            await conn.close()

@router.post('/{refresh_id}/cancel')
async def cancel(refresh_id:str,request:Request,response:Response):
    same_origin(request);response.headers.update(PRIVATE);conn=None
    try:
        conn=await db.connect();await initialize(conn)
        row=await conn.fetchrow('SELECT state FROM career_refreshes WHERE id=$1',refresh_id)
        if not row:raise HTTPException(404,'Refresh not found.',headers=PRIVATE)
        state=decode(row['state'])
        if state['status']=='running':
            await conn.execute('UPDATE career_refreshes SET cancel_requested=true WHERE id=$1',refresh_id)
            if refresh_id in _TASKS:
                task,event=_TASKS[refresh_id];event.set();task.cancel()
        return {'refresh':state,'cancel_requested':state['status']=='running'}
    except HTTPException:raise
    except Exception as exc:raise HTTPException(503,'Could not cancel the refresh. Retry shortly.',headers=PRIVATE) from exc
    finally:
        if conn:await conn.close()
