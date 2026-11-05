import copy,os,unittest,asyncio
from datetime import datetime,timezone
from unittest.mock import AsyncMock,patch
from uuid import uuid4
from fastapi.testclient import TestClient
from core import db
from hives.careers.app import app
from hives.careers import store
from hives.careers.search_index import build
from hives.careers.api import Search,search_catalog
from hives.careers.matching import Profile,match


def job():
    return {'id':'greenhouse:example:1','title':'Research Intern','company':'Example','source':'greenhouse','board':'example','role_type':'internship','location':'California, United States','description':'Requirements\nPython or SQL required.\nMust be enrolled in a degree program.\nMinimum GPA 3.0 on a 4.0 scale.\nExcellent communication experience required.\nPart-time paid internship.\nApply by December 20, 2030.','apply_url':'https://example.com/jobs/1','last_seen':datetime.now(timezone.utc).isoformat()}

class CompactParityTests(unittest.TestCase):
    def test_matching_and_filtering_preserve_results_without_source_prose(self):
        full=job();before=copy.deepcopy(full);summary,document=build(full)
        self.assertEqual(full,before);self.assertEqual(summary['description'],'');self.assertTrue(summary['has_description'])
        for profile in [Profile(),Profile(skills='Python | Built a project',enrolled=True,gpa=3.7),Profile(skills='SQL',enrolled=False,gpa=2.5)]:
            a,b=match(full,profile),match(summary,profile)
            for key in ['score','assessment','qualification_summary','breakdown','has_conflict','location_fit']:
                self.assertEqual(a[key],b[key],key)
            data={'boards':[],'jobs':[full]};compact={'boards':[],'jobs':[summary],'query_ids':{full['id']}}
            for extra in [{},{'career_fields':['science']},{'countries':['US']},{'opportunity_types':['research']},{'query':'Python'}]:
                self.assertEqual(search_catalog(data,Search(profile=profile,**extra))['total'],search_catalog(compact,Search(profile=profile,compact=True,**extra))['total'])
        page=search_catalog({'boards':[],'jobs':[summary]},Search(compact=True,profile=Profile(skills='Python')))['jobs'][0]
        self.assertNotIn('requirements',page);self.assertNotIn('qualification_snapshot',page)
        self.assertTrue(all(c['quote'] is None and c['quote_deferred'] for c in page['match']['checks']))
        self.assertIn('python',document)
    def test_details_recompute_private_match_from_complete_stored_posting(self):
        full={**job(),'open':False}
        with TestClient(app) as c,patch('hives.careers.api.store.get_job',new=AsyncMock(return_value=full)),patch('hives.careers.api.store.get_board',new=AsyncMock(return_value={'error':None})):
            r=c.post('/api/careers/opportunities/'+full['id']+'/details',json={'profile':{'skills':'Python'}})
            self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.headers['cache-control'],'no-store')
            row=r.json()['job'];self.assertEqual(row['description'],full['description']);self.assertFalse(row['description_deferred']);self.assertEqual(row['availability']['state'],'removed')
            self.assertTrue(any('Python' in check['quote'] for check in row['match']['checks']))
        with TestClient(app) as c,patch('hives.careers.api.store.get_job',new=AsyncMock(return_value=None)):
            self.assertEqual(c.post('/api/careers/opportunities/missing/details',json={}).status_code,404)

@unittest.skipUnless(os.getenv('CAREERS_DB_TEST')=='1','requires opt-in local Postgres')
class CompactStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_summary_and_literal_query_keep_source_timestamps_and_handle_legacy_writes(self):
        await store.initialize();employer={'name':'Search test','source':'greenhouse','board':'test_'+uuid4().hex};key='greenhouse:'+employer['board']
        full={**job(),'id':key+':1','board':employer['board'],'description':job()['description']+'\nStraße 100% lab_rate.','company':'Search test'}
        with patch('hives.careers.store.employers',return_value=[employer]):
            try:
                await store.save_snapshot(employer,[full]);raw=(await store.catalog())['jobs'][0];compact=await store.catalog(compact=True)
                small=compact['jobs'][0];self.assertEqual(small['description'],'');self.assertTrue(small['description_deferred']);self.assertEqual(raw['last_seen'],small['last_seen']);self.assertEqual(raw['changed_at'],small['changed_at'])
                self.assertEqual(compact['revision'],await store.catalog_revision(compact=True))
                for query in ['strasse','100%','lab_rate','California']:
                    self.assertIn(full['id'],await store.query_ids(query,compact=True))
                self.assertNotIn(full['id'],await store.query_ids('100_',compact=True))
                conn=await db.connect()
                try:await conn.execute("UPDATE career_jobs SET data=jsonb_set(data,'{description}','\"Legacy new text\"'::jsonb),changed_at=now() WHERE id=$1",full['id'])
                finally:await conn.close()
                fallback=(await store.catalog(compact=True))['jobs'][0]
                self.assertEqual(fallback['description'],'Legacy new text')
                self.assertIn(full['id'],await store.query_ids('legacy new',compact=True))
            finally:
                conn=await db.connect()
                try:
                    await conn.execute('DELETE FROM career_jobs WHERE board_key=$1',key);await conn.execute('DELETE FROM career_boards WHERE key=$1',key)
                finally:await conn.close()
