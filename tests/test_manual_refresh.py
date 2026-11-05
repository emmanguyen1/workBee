import asyncio,os,time,unittest
from unittest.mock import patch,AsyncMock
from uuid import uuid4
import httpx
from fastapi.testclient import TestClient
from core import db
from hives.careers import refresh,store
from hives.careers.app import app

class RefreshBoundaryTests(unittest.TestCase):
    def test_unknown_urls_and_cross_origin_requests_do_not_start_work(self):
        with TestClient(app) as c:
            self.assertEqual(c.post('/api/careers/refresh',json={'boards':['https://localhost/private']}).status_code,400)
            self.assertEqual(c.post('/api/careers/refresh',json={},headers={'Origin':'https://untrusted.example'}).status_code,403)
            self.assertEqual(c.post('/api/careers/refresh',json={'boards':['x'],'companies':['y']}).status_code,422)

@unittest.skipUnless(os.getenv('CAREERS_DB_TEST')=='1','requires opt-in local Postgres')
class ManualRefreshTests(unittest.TestCase):
    def setUp(self):
        self.schema='test_refresh_'+uuid4().hex
        self.base_connect=db.connect
        self.lock_patch=patch.object(refresh,'LOCK_KEY',int(uuid4().hex[:12],16));self.lock_patch.start()
        async def create():
            conn=await self.base_connect()
            try:await conn.execute('CREATE SCHEMA '+self.schema)
            finally:await conn.close()
        asyncio.run(create())
        async def isolated():
            conn=await self.base_connect();await conn.execute('SET search_path TO '+self.schema);return conn
        self.db_patch=patch.object(db,'connect',side_effect=isolated);self.db_patch.start()
        self.employer={'name':'Test employer','source':'greenhouse','board':'test_board'}
        self.sources_patch=patch.object(refresh,'employers',return_value=[self.employer]);self.sources_patch.start()
        self.job={'id':'greenhouse:test_board:1','title':'Policy Intern','company':'Test employer','location':'','description':'Old snapshot','role_type':'internship'}
        async def fixture():
            await store.initialize();await store.save_snapshot(self.employer,[self.job]);conn=await db.connect()
            try:
                await conn.execute("UPDATE career_boards SET checked_at=now()-interval '10 minutes',attempted_at=now()-interval '10 minutes'")
                await conn.execute("UPDATE career_jobs SET last_seen=now()-interval '40 minutes'")
            finally:await conn.close()
        asyncio.run(fixture())
        self.client=TestClient(app);self.client.__enter__()
    def tearDown(self):
        self.client.__exit__(None,None,None);self.sources_patch.stop();self.db_patch.stop();self.lock_patch.stop()
        async def cleanup():
            conn=await self.base_connect()
            try:await conn.execute('DROP SCHEMA '+self.schema+' CASCADE')
            finally:await conn.close()
        asyncio.run(cleanup())
    def wait(self,terminal=True):
        for _ in range(100):
            response=self.client.get('/api/careers/refresh');self.assertEqual(response.status_code,200,response.text);state=response.json()['refresh']
            if state and ((state['status']!='running') if terminal else any(s['status']=='running' for s in state['sources'])):return state
            time.sleep(.01)
        self.fail('Refresh did not reach expected state')
    def test_snapshot_refresh_and_cooldown_without_duplicate_fetch(self):
        fresh={**self.job,'description':'New public snapshot'}
        with patch.object(refresh,'fetch_board',new=AsyncMock(return_value=[fresh])) as fetch:
            started=self.client.post('/api/careers/refresh',json={'companies':['Test employer']});self.assertEqual(started.status_code,202,started.text)
            state=self.wait();self.assertEqual(state['status'],'completed');self.assertEqual(state['sources'][0]['status'],'refreshed')
            self.assertEqual(asyncio.run(store.get_job(self.job['id']))['description'],'New public snapshot')
            self.assertEqual(self.client.post('/api/careers/refresh',json={}).status_code,202)
            self.assertEqual(self.wait()['sources'][0]['status'],'skipped');self.assertEqual(fetch.await_count,1)
            statuses=self.client.get('/api/careers/refresh');self.assertEqual(statuses.headers['cache-control'],'no-store');self.assertTrue(statuses.json()['sources'][0]['checked_at'])
    def test_failure_preserves_open_snapshot(self):
        with patch.object(refresh,'fetch_board',new=AsyncMock(side_effect=httpx.ReadTimeout('private feed detail'))):
            self.client.post('/api/careers/refresh',json={});state=self.wait()
            self.assertEqual(state['sources'][0]['status'],'error')
            row=asyncio.run(store.get_job(self.job['id']));self.assertTrue(row['open']);self.assertEqual(row['description'],'Old snapshot')
            self.assertNotIn('private feed detail',str(state))
    def test_join_and_cancel_keep_previous_snapshot(self):
        async def blocked(*args,**kwargs):await asyncio.Future()
        with patch.object(refresh,'fetch_board',new=AsyncMock(side_effect=blocked)) as fetch:
            first=self.client.post('/api/careers/refresh',json={}).json()['refresh'];self.wait(terminal=False)
            second=self.client.post('/api/careers/refresh',json={}).json()
            self.assertTrue(second['joined']);self.assertEqual(first['id'],second['refresh']['id'])
            self.assertEqual(self.client.post('/api/careers/refresh/'+first['id']+'/cancel').status_code,200)
            self.assertEqual(self.wait()['status'],'cancelled')
            self.assertEqual(fetch.await_count,1)
            self.assertEqual(asyncio.run(store.get_job(self.job['id']))['description'],'Old snapshot')

    def test_cancel_preserves_completed_sources(self):
        second={'name':'Second employer','source':'greenhouse','board':'second_board'}
        async def partial(client,employer,**kwargs):
            if employer['board']=='test_board':return [{**self.job,'description':'Completed first source'}]
            await asyncio.Future()
        with patch.object(refresh,'employers',return_value=[self.employer,second]),patch.object(refresh,'fetch_board',new=AsyncMock(side_effect=partial)):
            state=self.client.post('/api/careers/refresh',json={}).json()['refresh']
            for _ in range(100):
                progress=self.client.get('/api/careers/refresh').json()['refresh']
                if progress['sources'][1]['status']=='running':break
                time.sleep(.01)
            else:self.fail('Second source never started')
            self.client.post('/api/careers/refresh/'+state['id']+'/cancel')
            done=self.wait();self.assertEqual(done['status'],'cancelled')
            self.assertEqual([s['status'] for s in done['sources']],['refreshed','cancelled'])
            self.assertEqual(asyncio.run(store.get_job(self.job['id']))['description'],'Completed first source')

    def test_abandoned_job_is_reported_as_interrupted(self):
        import json
        async def abandoned():
            conn=await db.connect()
            try:
                await refresh.initialize(conn)
                await conn.execute('INSERT INTO career_refreshes(id,state) VALUES ($1,$2::jsonb)','abandoned',json.dumps({'id':'abandoned','status':'running','sources':[],'total':0,'completed':0}))
            finally:await conn.close()
        asyncio.run(abandoned())
        state=self.client.get('/api/careers/refresh').json()['refresh']
        self.assertEqual(state['status'],'interrupted')
