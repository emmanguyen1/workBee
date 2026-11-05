import unittest
from fastapi.testclient import TestClient
from dashboard.app import app as kalshi
from hives.careers.app import app as careers
from hives.careers.geography import geography, preferred_matches
from hives.careers.api import Search, search_catalog
from hives.careers.accounts import Preferences


class WorkBeeTests(unittest.TestCase):
    def test_separate_websites_and_routes(self):
        with TestClient(careers) as client:
            self.assertIn('workBee', client.get('/').text)
            self.assertNotIn('Kalshi', client.get('/').text)
            self.assertEqual(client.get('/kalshi').status_code,404)
            self.assertEqual(client.get('/api/kalshi/portfolio').status_code,404)
            self.assertNotIn('City, state, or country',client.get('/').text)
        with TestClient(kalshi) as client:
            self.assertIn('Kalshi',client.get('/').text)
            self.assertNotIn('workBee',client.get('/').text)
            self.assertEqual(client.get('/careers').status_code,404)
            self.assertEqual(client.post('/api/careers/search',json={}).status_code,404)

    def test_explicit_states_countries_and_ambiguous_cities(self):
        for location, countries, regions in [('San Francisco, CA',['US'],['US-CA']),('Boston, Massachusetts',['US'],['US-MA']),('Toronto, ON, Canada',['CA'],['CA-ON']),('London, UK',['GB'],[]),('Berlin, Germany',['DE'],[]),('Remote',[],[]),('Cambridge',[],[]),('Washington, DC',['US'],['US-DC'])]:
            self.assertEqual(geography({'location':location}),{'countries':countries,'regions':regions},location)
        self.assertEqual(geography({'location':'Remote','countries':['IN']})['countries'],['IN'])
        self.assertTrue(preferred_matches('California',{'location':'San Francisco, CA'}))
        self.assertFalse(preferred_matches('Canada',{'location':'San Francisco, CA'}))

    def test_country_state_filters_and_facet_count_parity(self):
        def job(id,loc):return {'id':id,'title':'Marketing Intern','company':'Example','location':loc,'description':'','role_type':'internship'}
        data={'jobs':[job('1','San Francisco, CA'),job('2','Boston, MA'),job('3','Toronto, ON, Canada'),job('4','Cambridge')],'boards':[]}
        result=search_catalog(data,Search(country='US',region='US-CA'))
        self.assertEqual([j['id'] for j in result['jobs']],['1'])
        self.assertEqual(next(f['count'] for f in result['facets']['fields'] if f['value']=='marketing'),result['total'])
        self.assertEqual(search_catalog(data,Search(country='CA'))['total'],1)
        self.assertEqual(search_catalog(data,Search(country='unknown'))['total'],1)
        self.assertNotIn('locations',result['facets'])
        self.assertEqual(Preferences(country='US',region='US-CA').region,'US-CA')
