"""Server-side provider sign-in. Identities are linked by provider subject, never email."""
import base64
import hashlib
import json
import os
import re
import secrets
from time import monotonic
from typing import Literal
from urllib.parse import urlencode,urlparse

import httpx
import jwt
from fastapi import APIRouter,Request,Response,HTTPException
from fastapi.responses import RedirectResponse
from hives.careers import accounts

router=APIRouter(prefix='/api/account/oauth')
Provider=Literal['google','linkedin']
PROVIDERS={
 'google':{'name':'Google','authorize':'https://accounts.google.com/o/oauth2/v2/auth','token':'https://oauth2.googleapis.com/token','jwks':'https://www.googleapis.com/oauth2/v3/certs','userinfo':'https://openidconnect.googleapis.com/v1/userinfo','issuers':['https://accounts.google.com','accounts.google.com'],'pkce':True,'nonce':True},
 'linkedin':{'name':'LinkedIn','authorize':'https://www.linkedin.com/oauth/v2/authorization','token':'https://www.linkedin.com/oauth/v2/accessToken','jwks':'https://www.linkedin.com/oauth/openid/jwks','userinfo':'https://api.linkedin.com/v2/userinfo','issuers':['https://www.linkedin.com'],'pkce':False,'nonce':False},
}
_JWKS={}

class OAuthIssue(HTTPException):
    def __init__(self,reason):super().__init__(409,reason,headers=accounts.PRIVATE)


def public_url():
    value=os.getenv('WORKBEE_PUBLIC_URL','http://localhost:8001').strip().rstrip('/')
    parsed=urlparse(value)
    _=parsed.port
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path or not parsed.hostname:raise ValueError('Invalid public origin')
    if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in {'localhost','127.0.0.1','::1'}):raise ValueError('HTTPS required outside loopback')
    return value


def config(provider):
    prefix='WORKBEE_'+provider.upper()
    return {'client_id':os.getenv(prefix+'_CLIENT_ID','').strip(),'client_secret':os.getenv(prefix+'_CLIENT_SECRET','').strip(),'redirect_uri':public_url()+'/api/account/oauth/'+provider+'/callback'}


def configured(provider):
    try:c=config(provider);return bool(c['client_id'] and c['client_secret'])
    except ValueError:return False


def redirect(result,provider=None):
    response=RedirectResponse('/account?auth='+result,status_code=303,headers={**accounts.PRIVATE,'Referrer-Policy':'no-referrer'})
    if provider:response.delete_cookie('workbee_oauth_'+provider,path='/api/account/oauth')
    return response


async def initialize(conn):
    await conn.execute('''CREATE TABLE IF NOT EXISTS career_provider_identities (
      provider TEXT NOT NULL, subject TEXT NOT NULL, user_id BIGINT NOT NULL REFERENCES career_accounts(id) ON DELETE CASCADE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(provider,subject), UNIQUE(user_id,provider)
    );
    CREATE TABLE IF NOT EXISTS career_oauth_states (
      state_hash TEXT PRIMARY KEY, provider TEXT NOT NULL, browser_hash TEXT NOT NULL,
      nonce_hash TEXT NOT NULL, verifier TEXT NOT NULL, account_id BIGINT REFERENCES career_accounts(id) ON DELETE CASCADE,
      throttle_key TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL DEFAULT now()+interval '10 minutes'
    )''')


async def signing_key(client,provider,kid):
    cached=_JWKS.get(provider)
    keys=cached[1] if cached and monotonic()-cached[0]<3600 else []
    key=next((k for k in keys if k.get('kid')==kid),None)
    if key is None:
        if cached and monotonic()-cached[0]<15:raise ValueError('Unknown signing key')
        response=await client.get(PROVIDERS[provider]['jwks']);response.raise_for_status()
        if len(response.content)>1024*1024:raise ValueError('Invalid key document')
        keys=response.json()['keys']
        if not isinstance(keys,list) or len(keys)>100:raise ValueError('Invalid key document')
        _JWKS[provider]=(monotonic(),keys)
        key=next((k for k in keys if k.get('kid')==kid),None)
    if not key or key.get('kty')!='RSA' or key.get('use','sig')!='sig' or key.get('alg','RS256')!='RS256':raise ValueError('Invalid signing key')
    parsed=jwt.PyJWK.from_dict(key,algorithm='RS256').key
    if parsed.key_size<2048:raise ValueError('Invalid key size')
    return parsed


async def exchange(provider,code,ticket):
    c=config(provider);p=PROVIDERS[provider]
    fields={'grant_type':'authorization_code','code':code,'client_id':c['client_id'],'client_secret':c['client_secret'],'redirect_uri':c['redirect_uri']}
    if p['pkce']:fields['code_verifier']=ticket['verifier']
    async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
        response=await client.post(p['token'],data=fields);response.raise_for_status();tokens=response.json()
        token=tokens['id_token'];access=tokens.get('access_token','')
        if not isinstance(token,str) or len(token)>20000:raise ValueError('Invalid token')
        header=jwt.get_unverified_header(token)
        if header.get('alg')!='RS256' or header.get('crit') or not isinstance(header.get('kid'),str):raise ValueError('Unsupported token')
        key=await signing_key(client,provider,header['kid'])
        required=['iss','sub','aud','iat','exp']+(['nonce'] if p['nonce'] else [])
        claims=jwt.decode(token,key,algorithms=['RS256'],audience=c['client_id'],issuer=p['issuers'],options={'require':required},leeway=30)
        if not isinstance(claims['sub'],str) or not 1<=len(claims['sub'])<=255:raise ValueError('Invalid subject')
        if p['nonce'] and not secrets.compare_digest(accounts.token_hash(claims['nonce']),ticket['nonce_hash']):raise ValueError('Invalid nonce')
        if claims.get('azp') and claims['azp']!=c['client_id'] or isinstance(claims['aud'],list) and len(claims['aud'])>1 and claims.get('azp')!=c['client_id']:raise ValueError('Invalid authorized party')
        if claims.get('at_hash'):
            expected=base64.urlsafe_b64encode(hashlib.sha256(access.encode()).digest()[:16]).rstrip(b'=').decode()
            if not secrets.compare_digest(expected,claims['at_hash']):raise ValueError('Invalid access token binding')
        name=claims.get('name','')
        if not name and access:
            try:
                info=await client.get(p['userinfo'],headers={'Authorization':'Bearer '+access});info.raise_for_status();info=info.json()
                if info.get('sub')!=claims['sub']:raise ValueError('Subject mismatch')
                name=info.get('name','')
            except httpx.HTTPError:pass  # A display name is optional; signed subject is authoritative.
    return {'subject':claims['sub'],'name':re.sub(r'[\x00-\x1f\x7f]',' ',str(name)).strip()[:80]}


async def resolve(conn,provider,identity,account_id=None):
    subject=identity['subject']
    async with conn.transaction():
        if account_id:await conn.fetchrow('SELECT id FROM career_accounts WHERE id=$1 FOR UPDATE',account_id)
        lock=int.from_bytes(hashlib.sha256((provider+':'+subject).encode()).digest()[:8],'big',signed=True)
        await conn.execute('SELECT pg_advisory_xact_lock($1::bigint)',lock)
        existing=await conn.fetchrow('SELECT user_id FROM career_provider_identities WHERE provider=$1 AND subject=$2',provider,subject)
        if existing:
            if account_id and existing['user_id']!=account_id:raise OAuthIssue('identity_in_use')
            return await conn.fetchrow('SELECT * FROM career_accounts WHERE id=$1',existing['user_id'])
        if account_id:
            if await conn.fetchval('SELECT 1 FROM career_provider_identities WHERE user_id=$1 AND provider=$2',account_id,provider):raise OAuthIssue('provider_already_connected')
            row=await conn.fetchrow('SELECT * FROM career_accounts WHERE id=$1',account_id)
        else:
            row=None
            for _ in range(3):
                row=await conn.fetchrow("INSERT INTO career_accounts(username,password_hash,identity) VALUES ($1,'',$2::jsonb) ON CONFLICT(username) DO NOTHING RETURNING *",'bee_'+secrets.token_hex(8),json.dumps({'display_name':identity['name'],'school':'','headline':''}))
                if row:break
            if row is None:raise ValueError('Could not create account')
        await conn.execute('INSERT INTO career_provider_identities(provider,subject,user_id) VALUES ($1,$2,$3)',provider,subject,row['id'])
        return row


@router.get('/providers')
async def providers(request:Request,response:Response):
    response.headers.update(accounts.PRIVATE)
    async with accounts.connection() as conn:
        await initialize(conn);current=await accounts.user(conn,request,required=False)
        rows=await conn.fetch('SELECT provider,created_at FROM career_provider_identities WHERE user_id=$1',current['id']) if current else []
        connected={r['provider']:r['created_at'].isoformat() for r in rows}
        password=bool(current and current['password_hash'])
        return {'authenticated':bool(current),'password_enabled':password,'providers':[{'id':key,'name':p['name'],'enabled':configured(key),'connected':key in connected,'connected_at':connected.get(key),'can_disconnect':key in connected and (password or len(connected)>1)} for key,p in PROVIDERS.items()]}


@router.post('/{provider}/start')
async def start(provider:Provider,request:Request,intent:Literal['login','link']='login'):
    accounts.same_origin(request)
    if not configured(provider):return redirect('unavailable')
    if str(request.base_url).rstrip('/')!=public_url():return redirect('origin_mismatch')
    async with accounts.connection() as conn:
        await initialize(conn);current=await accounts.user(conn,request,required=False)
        if intent=='link' and not current:return redirect('signin_required')
        if intent=='login' and current:return redirect('already_signed_in')
        attempt=await accounts.throttle(conn,request,'oauth',provider)
        state=secrets.token_urlsafe(32);browser=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(64)
        await conn.execute('DELETE FROM career_oauth_states WHERE expires_at<now()')
        await conn.execute('INSERT INTO career_oauth_states(state_hash,provider,browser_hash,nonce_hash,verifier,account_id,throttle_key) VALUES ($1,$2,$3,$4,$5,$6,$7)',accounts.token_hash(state),provider,accounts.token_hash(browser),accounts.token_hash(nonce),verifier,current['id'] if intent=='link' else None,attempt)
    c=config(provider);params={'response_type':'code','client_id':c['client_id'],'redirect_uri':c['redirect_uri'],'scope':'openid profile','state':state}
    if PROVIDERS[provider]['nonce']:params['nonce']=nonce
    if PROVIDERS[provider]['pkce']:params.update(code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode(),code_challenge_method='S256')
    response=RedirectResponse(PROVIDERS[provider]['authorize']+'?'+urlencode(params),status_code=303,headers={**accounts.PRIVATE,'Referrer-Policy':'no-referrer'})
    response.set_cookie('workbee_oauth_'+provider,browser,max_age=600,httponly=True,secure=public_url().startswith('https:'),samesite='lax',path='/api/account/oauth')
    return response


@router.get('/{provider}/callback')
async def callback(provider:Provider,request:Request):
    state=request.query_params.get('state','');code=request.query_params.get('code','');browser=request.cookies.get('workbee_oauth_'+provider,'')
    if not configured(provider) or not re.fullmatch(r'[A-Za-z0-9_-]{40,100}',state) or not re.fullmatch(r'[A-Za-z0-9_-]{40,100}',browser) or len(code)>4096:return redirect('failed',provider)
    try:
        async with accounts.connection() as conn:
            await initialize(conn)
            ticket=await conn.fetchrow('DELETE FROM career_oauth_states WHERE state_hash=$1 AND provider=$2 AND browser_hash=$3 AND expires_at>now() RETURNING *',accounts.token_hash(state),provider,accounts.token_hash(browser))
            if ticket is None:return redirect('failed',provider)
            if request.query_params.get('error'):return redirect('cancelled',provider)
            if not code:return redirect('failed',provider)
            current=await accounts.user(conn,request,required=False)
            if ticket['account_id']:
                if not current or current['id']!=ticket['account_id']:return redirect('account_changed',provider)
            elif current:return redirect('already_signed_in',provider)
        identity=await exchange(provider,code,ticket)
        async with accounts.connection() as conn:
            await initialize(conn)
            # Check again after the provider request, before attaching an identity.
            current=await accounts.user(conn,request,required=False)
            if ticket['account_id'] and (not current or current['id']!=ticket['account_id']):return redirect('account_changed',provider)
            if not ticket['account_id'] and current:return redirect('already_signed_in',provider)
            row=await resolve(conn,provider,identity,ticket['account_id'])
            response=redirect('connected' if ticket['account_id'] else 'signed_in',provider)
            await accounts.create_session(conn,request,response,row['id'])
            await conn.execute('DELETE FROM career_auth_attempts WHERE key=$1',ticket['throttle_key'])
            return response
    except OAuthIssue as exc:return redirect(exc.detail,provider)
    except Exception:return redirect('failed',provider)


@router.post('/{provider}/disconnect')
async def disconnect(provider:Provider,request:Request,response:Response):
    accounts.same_origin(request);response.headers.update(accounts.PRIVATE)
    async with accounts.connection() as conn:
        await initialize(conn);current=await accounts.user(conn,request)
        async with conn.transaction():
            row=await conn.fetchrow('SELECT password_hash FROM career_accounts WHERE id=$1 FOR UPDATE',current['id'])
            if not row['password_hash'] and await conn.fetchval('SELECT count(*) FROM career_provider_identities WHERE user_id=$1',current['id'])<=1:
                raise HTTPException(409,'Connect another sign-in method before disconnecting this one.',headers=accounts.PRIVATE)
            await conn.execute('DELETE FROM career_provider_identities WHERE user_id=$1 AND provider=$2',current['id'],provider)
        return {'disconnected':provider}
