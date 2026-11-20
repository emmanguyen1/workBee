import asyncio,json,os,unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch,AsyncMock,MagicMock
import httpx
from fastapi.testclient import TestClient
from hives.careers.app import app
from hives.careers import bee
from hives.careers.api import Search,search_catalog

class BeeTests(unittest.TestCase):
    def setUp(self):bee._LIMITS.clear()
    def test_guide_is_honest_and_help_does_not_fetch_catalog(self):
        with patch.dict(os.environ,{'WORKBEE_GEMINI_API_KEY':'','GEMINI_API_KEY':'','WORKBEE_OPENAI_API_KEY':''}),patch.object(bee,'retrieve',new=AsyncMock()) as retrieve,TestClient(app) as c:
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
        with patch.dict(os.environ,{'WORKBEE_GEMINI_API_KEY':'test-placeholder'}),patch.object(bee,'retrieve',new=AsyncMock(return_value=rows)),patch.object(bee,'generate',new=AsyncMock(side_effect=httpx.ConnectError('private-provider-detail'))),TestClient(app) as c:
            r=c.post('/api/bee/ask',json={'question':'Find policy internships'})
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()['mode'],'guide')
            self.assertTrue(r.json()['provider_unavailable'])
            self.assertNotIn('private-provider-detail',r.text)
            self.assertNotIn('requirements_excerpt',r.text)
            self.assertEqual(r.json()['sources'][0]['apply_url'],'https://example.com/job')
    def test_same_origin_limits_and_bounded_messages(self):
        with patch.dict(os.environ,{'WORKBEE_GEMINI_API_KEY':'','GEMINI_API_KEY':'','WORKBEE_OPENAI_API_KEY':''}),TestClient(app) as c:
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

    def test_prep_pack_endpoint_returns_structured_strategy_and_outreach(self):
        job = {"id": "greenhouse:acme:1", "title": "Software Intern", "company": "Acme Corp", "career_field": "software", "requirements": [{"skills": ["Python", "Docker"], "quote": "Must know Python"}]}
        with patch.dict(os.environ, {'WORKBEE_GEMINI_API_KEY': '', 'GEMINI_API_KEY': '', 'WORKBEE_OPENAI_API_KEY': ''}), patch('hives.careers.bee.store.get_job', new=AsyncMock(return_value=job)), TestClient(app) as c:
            res = c.post('/api/bee/prep', json={"job_id": "greenhouse:acme:1", "profile": {"skills": [{"skill": "Python", "evidence": "Built web service"}]}})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["company"], "Acme Corp")
            self.assertIn("ats_strategy", data)
            self.assertTrue(any("Python" in s for s in data["ats_strategy"]["strengths"]))
            self.assertIn("outreach", data)
            self.assertIn("Acme Corp", data["outreach"]["message"])
            self.assertEqual(len(data["interview_prep"]), 3)

    def test_email_subscription_endpoint(self):
        with TestClient(app) as c:
            # Valid email
            res = c.post('/api/careers/subscribe', json={'email': 'student@mit.edu'})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data['status'], 'subscribed')
            self.assertEqual(data['email'], 'student@mit.edu')
            self.assertIn('drop alerts', data['message'])

            # Invalid email format
            res_bad = c.post('/api/careers/subscribe', json={'email': 'not-an-email'})
            self.assertEqual(res_bad.status_code, 400)

class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_responses_request_does_not_store_or_attach_private_state(self):
        mock_interaction=MagicMock()
        mock_interaction.model_dump.return_value={'steps':[{'type':'model_output','content':[{'type':'text','text':'Ask about your preferred field.'}]}]}
        mock_client=MagicMock()
        mock_client.aio.interactions.create=AsyncMock(return_value=mock_interaction)
        with patch.dict(os.environ,{'WORKBEE_GEMINI_API_KEY':'test-placeholder'}),patch('google.genai.Client',return_value=mock_client) as mock_cls:
            result=await bee.generate(bee.Ask(question='Find internships',web_search=False),{'opportunities':[]})
            self.assertEqual(result['answer'],'Ask about your preferred field.')
            self.assertFalse(result['web_searched'])
            mock_cls.assert_called_once_with(api_key='test-placeholder')
            kwargs=mock_client.aio.interactions.create.call_args.kwargs
            self.assertFalse(kwargs['store'])
            self.assertIsNone(kwargs['tools'])
            input_data=json.loads(kwargs['input'])
            self.assertEqual(input_data['workbee_context'],{'opportunities':[]})
            self.assertNotIn('test-placeholder',json.dumps(kwargs['input']))

class CommunityTests(unittest.TestCase):
    def test_recent_opt_in_does_not_promote_community_to_employer_verified(self):
        now=datetime.now(timezone.utc)
        def row(id,age):return {'id':id,'title':'Marketing Intern','company':'Example','location':'','description':'','source':'simplify','board':'summer2027','role_type':'internship','last_seen':(now-timedelta(minutes=age)).isoformat()}
        data={'jobs':[row('fresh',1),row('old',40)],'boards':[{'key':'simplify:summer2027','error':None}]}
        self.assertEqual(search_catalog(data,Search(current_only=True))['total'],0)
        result=search_catalog(data,Search(current_only=True,include_community=True))
        self.assertEqual([j['id'] for j in result['jobs']],['fresh'])
        self.assertEqual(result['jobs'][0]['availability']['state'],'community')

class ResourceAssistantTests(unittest.TestCase):
    def setUp(self):bee._LIMITS.clear()
    def test_general_questions_do_not_become_job_searches(self):
        with patch.dict(os.environ,{'WORKBEE_GEMINI_API_KEY':'','GEMINI_API_KEY':'','WORKBEE_OPENAI_API_KEY':''}),patch.object(bee,'retrieve',new=AsyncMock()) as retrieve,TestClient(app) as c:
            r=c.post('/api/bee/ask',json={'question':'What is photosynthesis?'})
            self.assertEqual(r.status_code,200);self.assertEqual(r.json()['intent'],'general')
            self.assertIsNone(r.json()['search']);self.assertFalse(r.json()['web_searched'])
            self.assertIn('local-guide mode',r.json()['answer']);retrieve.assert_not_awaited()
            self.assertEqual(c.get('/careers/assets/bee-logic.mjs').status_code,200)
    def test_resume_advice_is_distinct_from_product_help(self):
        with patch.dict(os.environ,{'WORKBEE_GEMINI_API_KEY':'','GEMINI_API_KEY':'','WORKBEE_OPENAI_API_KEY':''}),patch.object(bee,'retrieve',new=AsyncMock()) as retrieve,TestClient(app) as c:
            data=c.post('/api/bee/ask',json={'question':'How do I write a resume for my first internship?'}).json()
            self.assertIsNone(data['topic']);self.assertEqual(data['intent'],'advice')
            self.assertTrue(data['resources']);self.assertIn('Never invent',data['answer']);retrieve.assert_not_awaited()
            self.assertEqual(c.post('/api/bee/ask',json={'question':'How do I import my resume?'}).json()['topic'],'resume')
    def test_research_resources_are_not_open_postings(self):
        with patch.dict(os.environ,{'WORKBEE_GEMINI_API_KEY':'','GEMINI_API_KEY':'','WORKBEE_OPENAI_API_KEY':''}),TestClient(app) as c:
            data=c.post('/api/bee/ask',json={'question':'How do I contact a research lab?'}).json()
            self.assertEqual(data['sources'],[]);self.assertIn('not verified open positions',data['answer'])
            self.assertTrue(any('nsf.gov' in r['url'] for r in data['resources']))
    def test_followup_uses_recent_search_without_polluting_advice(self):
        history=[bee.Turn(role='user',text='Find public health internships')]
        intent,query=bee.question_intent('What about remote?',history)
        self.assertEqual(intent,'catalog');self.assertEqual(bee.search_plan(query)['workplaces'],['remote'])
        self.assertEqual(bee.question_intent('How do I prepare for an interview?',history)[0],'advice')
    def test_ai_general_answer_does_not_read_catalog(self):
        result={'answer':'Photosynthesis converts light energy.','citations':[],'web_searched':False}
        with patch.dict(os.environ,{'WORKBEE_GEMINI_API_KEY':'test-placeholder'}),patch.object(bee,'retrieve',new=AsyncMock()) as retrieve,patch.object(bee,'generate',new=AsyncMock(return_value=result)) as generate,TestClient(app) as c:
            data=c.post('/api/bee/ask',json={'question':'What is photosynthesis?','web_search':False}).json()
            self.assertEqual(data['answer'],result['answer']);self.assertEqual(data['mode'],'ai');retrieve.assert_not_awaited()
            self.assertFalse(generate.await_args.args[0].web_search)
    def test_citation_offsets_and_unsafe_links(self):
        data=bee.provider_answer({'output':[{'type':'message','content':[{'type':'output_text','text':'First.'},{'type':'output_text','text':'Next [1].','annotations':[{'type':'url_citation','start_index':5,'end_index':8,'url':'https://example.org','title':'Source'},{'type':'url_citation','start_index':5,'end_index':8,'url':'https://user:secret@example.org','title':'bad'},{'type':'url_citation','start_index':-1,'end_index':2,'url':'javascript:alert(1)','title':'bad'}]}]}]})
        self.assertEqual(data['answer'],'First.\nNext [1].');self.assertEqual(len(data['citations']),1)
        c=data['citations'][0];self.assertEqual(data['answer'][c['start']:c['end']],'[1]')

class WebProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_web_tool_and_provenance(self):
        mock_interaction=MagicMock()
        mock_interaction.model_dump.return_value={'steps':[{'type':'google_search_call'},{'type':'model_output','content':[{'type':'text','text':'Read this [source].','annotations':[{'type':'url_citation','start_index':10,'end_index':18,'url':'https://www.nsf.gov/','title':'NSF'}]}]}]}
        mock_client=MagicMock()
        mock_client.aio.interactions.create=AsyncMock(return_value=mock_interaction)
        with patch.dict(os.environ,{'WORKBEE_GEMINI_API_KEY':'test-placeholder'}),patch('google.genai.Client',return_value=mock_client):
            result=await bee.generate(bee.Ask(question='Research current programs'),{'intent':'advice'})
            self.assertTrue(result['web_searched'])
            self.assertEqual(result['citations'][0]['url'],'https://www.nsf.gov/')
            kwargs=mock_client.aio.interactions.create.call_args.kwargs
            self.assertFalse(kwargs['store'])
            self.assertEqual(kwargs['tools'],[{'type':'google_search'}])
