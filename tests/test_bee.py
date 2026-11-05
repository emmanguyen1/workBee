import asyncio,json,os,unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch,AsyncMock
import httpx
from fastapi.testclient import TestClient
from hives.careers.app import app
from hives.careers import bee
from hives.careers.api import Search,search_catalog

class BeeTests(unittest.TestCase):
    def setUp(self):bee._LIMITS.clear()
    def test_guide_is_honest_and_help_does_not_fetch_catalog(self):
        with patch.dict(os.environ,{'WORKBEE_OPENAI_API_KEY':''}),patch.object(bee,'retrieve',new=AsyncMock()) as retrieve,TestClient(app) as c:
            self.assertEqual(c.get('/api/bee/status').json()['mode'],'guide')
            response=c.post('/api/bee/ask',json={'question':'How do I import my resume?'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['cache-control'],'no-store')
            self.assertIn('server-side API key',response.json()['notice'])
            self.assertEqual(response.json()['topic'],'resume')
            retrieve.assert_not_awaited()
            self.assertNotIn('bee-note',c.get('/').text)
            self.assertEqual(c.get('/careers/assets/bee.mjs').status_code,200)
    def test_sources_are_grounded_and_provider_errors_are_sanitized(self):
        rows=[{'id':'one','title':'Policy Intern','company':'Example','apply_url':'https://example.com/job','requirements_excerpt':'Public requirements'}]
        with patch.dict(os.environ,{'WORKBEE_OPENAI_API_KEY':'test-placeholder'}),patch.object(bee,'retrieve',new=AsyncMock(return_value=rows)),patch.object(bee,'generate',new=AsyncMock(side_effect=httpx.ConnectError('private-provider-detail'))),TestClient(app) as c:
            r=c.post('/api/bee/ask',json={'question':'Find policy internships'})
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()['mode'],'guide')
            self.assertTrue(r.json()['provider_unavailable'])
            self.assertNotIn('private-provider-detail',r.text)
            self.assertNotIn('requirements_excerpt',r.text)
            self.assertEqual(r.json()['sources'][0]['apply_url'],'https://example.com/job')
    def test_same_origin_limits_and_bounded_messages(self):
        with patch.dict(os.environ,{'WORKBEE_OPENAI_API_KEY':''}),TestClient(app) as c:
            self.assertEqual(c.post('/api/bee/ask',json={'question':'How do I compare?'},headers={'Origin':'https://untrusted.example'}).status_code,403)
            self.assertEqual(c.post('/api/bee/ask',json={'question':'x'*1001}).status_code,422)
            for i in range(12):self.assertEqual(c.post('/api/bee/ask',json={'question':'How do I compare?'}).status_code,200)
            self.assertEqual(c.post('/api/bee/ask',json={'question':'How do I compare?'}).status_code,429)
    def test_natural_question_maps_to_read_only_search(self):
        p=bee.search_plan('Find paid remote public health internships')
        self.assertEqual(p['career_fields'],['healthcare'])
        self.assertEqual(p['opportunity_types'],['internship'])
        self.assertEqual(p['workplaces'],['remote'])
        self.assertEqual(p['pay'],'paid')

class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_responses_request_does_not_store_or_attach_private_state(self):
        def handle(request):
            payload=json.loads(request.content)
            self.assertEqual(request.headers['authorization'],'Bearer test-placeholder')
            self.assertFalse(payload['store'])
            self.assertNotIn('test-placeholder',json.dumps(payload))
            self.assertEqual(json.loads(payload['input'])['workbee_context'],{'opportunities':[]})
            return httpx.Response(200,json={'output':[{'type':'message','content':[{'type':'output_text','text':'Ask about your preferred field.'}]}]})
        client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
        with patch.dict(os.environ,{'WORKBEE_OPENAI_API_KEY':'test-placeholder'}),patch.object(bee.httpx,'AsyncClient',return_value=client):
            self.assertEqual(await bee.generate(bee.Ask(question='Find internships'),{'opportunities':[]}),'Ask about your preferred field.')

class CommunityTests(unittest.TestCase):
    def test_recent_opt_in_does_not_promote_community_to_employer_verified(self):
        now=datetime.now(timezone.utc)
        def row(id,age):return {'id':id,'title':'Marketing Intern','company':'Example','location':'','description':'','source':'simplify','board':'summer2027','role_type':'internship','last_seen':(now-timedelta(minutes=age)).isoformat()}
        data={'jobs':[row('fresh',1),row('old',40)],'boards':[{'key':'simplify:summer2027','error':None}]}
        self.assertEqual(search_catalog(data,Search(current_only=True))['total'],0)
        result=search_catalog(data,Search(current_only=True,include_community=True))
        self.assertEqual([j['id'] for j in result['jobs']],['fresh'])
        self.assertEqual(result['jobs'][0]['availability']['state'],'community')
