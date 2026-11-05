import asyncio,copy,unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import AsyncMock,patch
from hives.careers.catalog import PublicCatalogCache,prepare
from hives.careers.api import search_catalog,Search
from hives.careers.matching import Profile


def data():
    return {'jobs':[{'id':k,'title':'Software Intern','company':'Example','description':'Requirements\n'+skill+' required','role_type':'internship','location':'California, United States','source':'greenhouse','board':'example','last_seen':datetime.now(timezone.utc).isoformat()} for k,skill in [('python','Python'),('sql','SQL')]],'boards':[{'key':'greenhouse:example','error':None}]}

class PublicCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_misses_load_once_and_results_are_not_personal(self):
        raw=data();clock=[0];cache=PublicCatalogCache(clock=lambda:clock[0])
        async def load(**kwargs):await asyncio.sleep(0);return copy.deepcopy(raw)
        with patch('hives.careers.catalog.store.catalog',new=AsyncMock(side_effect=load)) as loader:
            values=await asyncio.gather(*(cache.get(current_only=True,include_community=False) for _ in range(8)))
            self.assertEqual(loader.await_count,1)
            self.assertEqual(sum(not hit for public,hit in values),1)
            public=values[0][0]
            a=search_catalog(public,Search(role_type='all',profile=Profile(skills='Python')))
            b=search_catalog(public,Search(role_type='all',profile=Profile(skills='SQL')))
            self.assertEqual(a['jobs'][0]['id'],'python')
            self.assertEqual(b['jobs'][0]['id'],'sql')
            self.assertTrue(all('match' not in j for j in public['jobs']))
            self.assertNotIn('geography',raw['jobs'][0])
            clock[0]=61
            await cache.get(current_only=True,include_community=False)
            self.assertEqual(loader.await_count,2)
    async def test_public_write_epoch_invalidates_and_cache_is_bounded(self):
        epoch=[1];cache=PublicCatalogCache()
        with patch('hives.careers.catalog.store.catalog',new=AsyncMock(side_effect=lambda **kw:data())) as loader,patch('hives.careers.catalog.store.catalog_epoch',side_effect=lambda:epoch[0]):
            await cache.get(current_only=True)
            epoch[0]=2
            await cache.get(current_only=True)
            self.assertEqual(loader.await_count,2)
            await cache.get(current_only=False)
            await cache.get(current_only=False,include_community=True)
            self.assertLessEqual(len(cache.entries),2)
    async def test_clock_freshness_is_rechecked_on_prepared_data(self):
        raw=data();public=prepare(raw)
        now=datetime.now(timezone.utc)
        with patch('hives.careers.api.datetime') as clock:
            clock.now.return_value=now+timedelta(minutes=31)
            self.assertEqual(search_catalog(public,Search(current_only=True))['total'],0)

    async def test_lightweight_revision_keeps_unchanged_catalog_and_detects_writes(self):
        clock=[0];revision=['one'];cache=PublicCatalogCache(clock=lambda:clock[0])
        def loaded(**kwargs):return {**data(),'revision':revision[0]}
        with patch('hives.careers.catalog.store.catalog',new=AsyncMock(side_effect=loaded)) as loader,patch('hives.careers.catalog.store.catalog_revision',new=AsyncMock(side_effect=lambda **kw:revision[0])) as check:
            await cache.get(current_only=True)
            clock[0]=61
            public,hit=await cache.get(current_only=True)
            self.assertTrue(hit);self.assertEqual(loader.await_count,1);self.assertEqual(check.await_count,1)
            revision[0]='two';clock[0]=122
            public,hit=await cache.get(current_only=True)
            self.assertFalse(hit);self.assertEqual(loader.await_count,2)
            clock[0]=500
            await cache.get(current_only=True)
            self.assertEqual(loader.await_count,3)
