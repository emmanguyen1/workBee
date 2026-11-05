import asyncio,base64,json,os,time,unittest
from urllib.parse import urlparse,parse_qs
from unittest.mock import patch
from uuid import uuid4

import httpx,jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from core import db
from hives.careers import oauth
from hives.careers.app import app

KEY=rsa.generate_private_key(public_exponent=65537,key_size=2048)
JWK={**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key())),'kid':'test-key','alg':'RS256','use':'sig'}
ENV={'WORKBEE_PUBLIC_URL':'http://localhost:8001','WORKBEE_GOOGLE_CLIENT_ID':'google-test-id','WORKBEE_GOOGLE_CLIENT_SECRET':'google-test-secret','WORKBEE_LINKEDIN_CLIENT_ID':'linkedin-test-id','WORKBEE_LINKEDIN_CLIENT_SECRET':'linkedin-test-secret'}
ASYNC_CLIENT=httpx.AsyncClient

class ProviderProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):oauth._JWKS.clear()
    async def check(self,provider='google',changes=None,nonce='test-nonce'):
        p=oauth.PROVIDERS[provider];now=int(time.time())
        claims={'iss':p['issuers'][0],'aud':ENV['WORKBEE_'+provider.upper()+'_CLIENT_ID'],'sub':'test-subject','iat':now,'exp':now+300,'name':'Test Student'}
        if provider=='google':claims['nonce']=nonce
        claims.update(changes or {})
        token=jwt.encode(claims,KEY,algorithm='RS256',headers={'kid':'test-key'})
        def handle(request):
            if str(request.url)==p['token']:
                fields=parse_qs(request.content.decode());self.assertEqual(fields['client_secret'][0],ENV['WORKBEE_'+provider.upper()+'_CLIENT_SECRET'])
                self.assertEqual('code_verifier' in fields,p['pkce'])
                return httpx.Response(200,json={'id_token':token,'access_token':'test-access-token'})
            self.assertEqual(str(request.url),p['jwks']);return httpx.Response(200,json={'keys':[JWK]})
        with patch.dict(os.environ,ENV),patch.object(oauth.httpx,'AsyncClient',side_effect=lambda **kw:ASYNC_CLIENT(transport=httpx.MockTransport(handle),**kw)):
            return await oauth.exchange(provider,'test-code',{'verifier':'test-verifier','nonce_hash':oauth.accounts.token_hash('test-nonce')})
    async def test_google_and_linkedin_verified_subjects(self):
        self.assertEqual((await self.check())['subject'],'test-subject')
        self.assertEqual((await self.check('linkedin'))['name'],'Test Student')
    async def test_wrong_audience_issuer_nonce_expiry_and_authorized_party_fail(self):
        for change in [{'aud':'wrong'},{'iss':'https://untrusted.example'},{'exp':int(time.time())-120},{'aud':[ENV['WORKBEE_GOOGLE_CLIENT_ID'],'other']}]:
            with self.subTest(change=change),self.assertRaises(jwt.PyJWTError if 'aud' not in change or isinstance(change['aud'],str) else ValueError):await self.check(changes=change)
        with self.assertRaises(ValueError):await self.check(nonce='wrong-nonce')

class SignInBoundaries(unittest.TestCase):
    def test_unconfigured_and_cross_origin_start(self):
        with patch.dict(os.environ,{'WORKBEE_GOOGLE_CLIENT_ID':'','WORKBEE_GOOGLE_CLIENT_SECRET':''}),TestClient(app) as c:
            self.assertEqual(c.post('/api/account/oauth/google/start',follow_redirects=False).headers['location'],'/account?auth=unavailable')
            self.assertEqual(c.post('/api/account/oauth/google/start',headers={'Origin':'https://untrusted.example'}).status_code,403)
    def test_callback_has_no_open_redirect_or_error_reflection(self):
        with TestClient(app) as c:
            r=c.get('/api/account/oauth/google/callback?state=bad&error=private-error&next=https://untrusted.example',follow_redirects=False)
            self.assertEqual(r.headers['location'],'/account?auth=failed');self.assertEqual(r.headers['referrer-policy'],'no-referrer');self.assertNotIn('private-error',r.text)

@unittest.skipUnless(os.getenv('CAREERS_DB_TEST')=='1','requires opt-in local Postgres')
class OAuthLifecycleTests(unittest.TestCase):
    def setUp(self):
        oauth._JWKS.clear();self.schema='test_oauth_'+uuid4().hex;self.original_connect=db.connect
        async def create():
            c=await self.original_connect()
            try:await c.execute('CREATE SCHEMA '+self.schema)
            finally:await c.close()
        asyncio.run(create())
        async def isolated():
            c=await self.original_connect();await c.execute('SET search_path TO '+self.schema);return c
        self.db_patch=patch.object(db,'connect',side_effect=isolated);self.db_patch.start()
        self.env_patch=patch.dict(os.environ,ENV);self.env_patch.start()
        self.subject='subject-one';self.nonce='';self.bad_nonce=False;self.token_calls=0
        def provider(request):
            p=next((p for p in oauth.PROVIDERS.values() if str(request.url) in {p['token'],p['jwks']}),None)
            if not p:raise AssertionError('Unexpected provider URL')
            if str(request.url)==p['jwks']:return httpx.Response(200,json={'keys':[JWK]})
            self.token_calls+=1;fields=parse_qs(request.content.decode());now=int(time.time())
            claims={'iss':p['issuers'][0],'aud':fields['client_id'][0],'sub':self.subject,'iat':now,'exp':now+300,'name':'Test Student','email':'same@example.test'}
            if p['nonce']:claims['nonce']='wrong' if self.bad_nonce else self.nonce
            return httpx.Response(200,json={'id_token':jwt.encode(claims,KEY,algorithm='RS256',headers={'kid':'test-key'}),'access_token':'test-access'})
        self.transport_patch=patch.object(oauth.httpx,'AsyncClient',side_effect=lambda **kw:ASYNC_CLIENT(transport=httpx.MockTransport(provider),**kw));self.transport_patch.start()
        self.client=TestClient(app,base_url='http://localhost:8001',follow_redirects=False);self.client.__enter__()
    def tearDown(self):
        self.client.__exit__(None,None,None);self.transport_patch.stop();self.env_patch.stop();self.db_patch.stop()
        async def cleanup():
            c=await self.original_connect()
            try:await c.execute('DROP SCHEMA '+self.schema+' CASCADE')
            finally:await c.close()
        asyncio.run(cleanup())
    def begin(self,provider='google',intent='login'):
        r=self.client.post('/api/account/oauth/'+provider+'/start?intent='+intent)
        self.assertEqual(r.status_code,303,r.text);self.assertIn(oauth.PROVIDERS[provider]['authorize'],r.headers['location'])
        params=parse_qs(urlparse(r.headers['location']).query);self.nonce=params.get('nonce',[''])[0]
        self.assertIn('HttpOnly',r.headers['set-cookie']);return params['state'][0]
    def finish(self,state,provider='google'):
        return self.client.get('/api/account/oauth/'+provider+'/callback',params={'state':state,'code':'test-code'})
    def register(self,name='local_student'):
        r=self.client.post('/api/account/register',json={'username':name,'password':'a-long-test-password'})
        self.assertEqual(r.status_code,200,r.text)
    def test_signup_return_login_and_last_method_protection(self):
        state=self.begin();self.assertEqual(self.finish(state).headers['location'],'/account?auth=signed_in')
        original=self.client.get('/api/account/session').json();self.assertEqual(original['user']['display_name'],'Test Student')
        self.assertEqual(self.client.post('/api/account/oauth/google/disconnect').status_code,409)
        self.client.post('/api/account/logout');state=self.begin();self.finish(state)
        self.assertEqual(self.client.get('/api/account/session').json()['user']['username'],original['user']['username'])
        state=self.begin('linkedin','link');self.assertEqual(self.finish(state,'linkedin').headers['location'],'/account?auth=connected')
        self.assertEqual(self.client.post('/api/account/oauth/google/disconnect').status_code,200)
        self.assertEqual(self.client.post('/api/account/oauth/linkedin/disconnect').status_code,409)
    def test_existing_profile_is_preserved_when_linking(self):
        self.register();saved=self.client.put('/api/account/state',json={'profile':{'skills':'Python | Built a project'},'preferences':{'countries':['US']},'identity':{'display_name':'Existing name','school':'Example school'},'revision':0})
        self.assertEqual(saved.status_code,200,saved.text)
        before=self.client.get('/api/account/session').json();state=self.begin(intent='link');self.finish(state)
        after=self.client.get('/api/account/session').json()
        self.assertEqual(before['profile'],after['profile']);self.assertEqual(before['preferences'],after['preferences']);self.assertEqual(before['user'],after['user']);self.assertEqual(before['revision'],after['revision'])
    def test_state_binding_replay_expiry_and_nonce(self):
        state=self.begin()
        with TestClient(app,base_url='http://localhost:8001',follow_redirects=False) as other:
            r=other.get('/api/account/oauth/google/callback',params={'state':state,'code':'test-code'});self.assertEqual(r.headers['location'],'/account?auth=failed')
        self.assertEqual(self.finish(state).headers['location'],'/account?auth=signed_in')
        self.assertEqual(self.finish(state).headers['location'],'/account?auth=failed');self.assertEqual(self.token_calls,1)
        self.client.post('/api/account/logout');state=self.begin()
        async def expire():
            c=await db.connect()
            try:await c.execute("UPDATE career_oauth_states SET expires_at=now()-interval '1 minute'")
            finally:await c.close()
        asyncio.run(expire());self.assertEqual(self.finish(state).headers['location'],'/account?auth=failed')
        state=self.begin();self.bad_nonce=True;self.assertEqual(self.finish(state).headers['location'],'/account?auth=failed')
        self.assertIsNone(self.client.get('/api/account/session').json()['user'])
    def test_matching_email_does_not_merge_and_conflicting_link_is_rejected(self):
        self.finish(self.begin());first=self.client.get('/api/account/session').json()['user']['username'];self.client.post('/api/account/logout')
        self.subject='subject-two';self.finish(self.begin());second=self.client.get('/api/account/session').json()['user']['username'];self.assertNotEqual(first,second)
        self.client.post('/api/account/logout');self.register();self.subject='subject-one'
        r=self.finish(self.begin(intent='link'));self.assertEqual(r.headers['location'],'/account?auth=identity_in_use')
        self.assertEqual(self.client.get('/api/account/session').json()['user']['username'],'local_student')
    def test_logout_during_link_does_not_attach_identity(self):
        self.register();state=self.begin(intent='link');self.client.post('/api/account/logout')
        self.assertEqual(self.finish(state).headers['location'],'/account?auth=account_changed');self.assertEqual(self.token_calls,0)
