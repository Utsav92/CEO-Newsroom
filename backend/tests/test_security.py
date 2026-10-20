import asyncio,hashlib,hmac,time
from datetime import datetime,timedelta,timezone
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from starlette.requests import Request
from app import main,accounts,billing,security,ingestion
from app.database import LoginSession,AudioGrant

@pytest.fixture
def secured(db,monkeypatch):
    monkeypatch.setattr(main,'AUTH_REQUIRED',True);monkeypatch.setattr(accounts,'SCRYPT_N',1024)
    monkeypatch.setattr(accounts,'ALLOW_REMOTE_REGISTRATION',False)
    monkeypatch.setattr(billing,'STRIPE_KEY','');monkeypatch.setattr(billing,'STRIPE_WEBHOOK_SECRET','')
    return db

def client():return TestClient(main.app,client=('127.0.0.1',50000))
def csrf(c):return {'X-Newsroom-Token':c.get('/api/session').json()['token']}
def signup(c,email='reader@example.test'):
    response=c.post('/api/auth/register',headers=csrf(c),json={'name':'Reader','email':email,'password':'Private test password 123'})
    assert response.status_code==200,response.text
    return response.json()['user']

def test_browser_headers_and_api_no_store_apply_to_rejections(secured):
    c=client();r=c.get('/api/news')
    assert r.status_code==401 and r.headers['cache-control']=='no-store'
    assert r.headers['x-frame-options']=='DENY' and r.headers['x-content-type-options']=='nosniff'
    csp=r.headers['content-security-policy']
    assert "script-src 'self';" in csp and "frame-ancestors 'none'" in csp and 'https://www.youtube.com' in csp
    assert r.headers['x-request-id'] and 'camera=()' in r.headers['permissions-policy']
    assert c.get('/docs').status_code==404 and c.get('/openapi.json').status_code==404
    assert c.get('/assets/missing.js',headers={'Host':'attacker.example'}).status_code==403

def test_cross_site_api_reads_and_writes_are_denied(secured):
    c=client()
    assert c.get('/api/auth/session',headers={'Sec-Fetch-Site':'cross-site'}).status_code==403
    assert c.post('/api/auth/login',headers={'Sec-Fetch-Site':'cross-site'},json={}).status_code==403

def test_csrf_is_bound_to_the_current_login_cookie_and_cannot_be_swapped(secured):
    c=client();anonymous=csrf(c);signup(c)
    assert c.put('/api/auth/profile',headers=anonymous,json={'name':'Changed'}).status_code==403
    assert c.put('/api/auth/profile',headers=csrf(c),json={'name':'Changed'}).status_code==200
    other=client();signup(other,'other@example.test');token=csrf(other)['X-Newsroom-Token']
    c.cookies.set('newsroom_session',token,domain='testserver.local',path='/')
    assert c.put('/api/auth/profile',headers={'X-Newsroom-Token':token},json={'name':'Stolen token'}).status_code==403

def test_csrf_rejects_expired_future_and_modified_signatures():
    def signed(stamp):
        value=str(stamp)+'.nonce.'+hashlib.sha256(b'cookie').hexdigest()
        return str(stamp)+'.nonce.'+hmac.new(security.CSRF_SECRET,value.encode(),hashlib.sha256).hexdigest()
    assert not security.valid_csrf(signed(int(time.time())-90000),'cookie')
    assert not security.valid_csrf(signed(int(time.time())+3600),'cookie')
    token=security.csrf_token('cookie');assert security.valid_csrf(token,'cookie')
    assert not security.valid_csrf(token+'x','cookie') and not security.valid_csrf(token,'different')

def test_bodies_are_bounded_with_and_without_content_length(secured):
    c=client()
    assert c.post('/api/auth/login',content=b'x'*131073).status_code==413
    assert c.post('/api/auth/login',content=iter([b'x'*70000,b'y'*70000])).status_code==413
    assert c.post('/api/billing/webhook',content=b'x',headers={'Content-Length':'bad'}).status_code==400
    assert c.post('/api/billing/webhook',content=b'x'*1_000_001).status_code==413

def test_remote_plain_http_and_spoofed_forwarded_headers_are_rejected(secured,monkeypatch):
    monkeypatch.setattr(main,'PUBLIC_APP_URL','https://newsroom.example.test')
    c=TestClient(main.app,base_url='http://newsroom.example.test')
    assert c.get('/api/auth/session',headers={'X-Forwarded-Proto':'https'}).status_code==403
    secure=TestClient(main.app,base_url='https://newsroom.example.test')
    r=secure.get('/api/session')
    assert r.status_code==200 and 'Secure' in r.headers['set-cookie'] and 'HttpOnly' in r.headers['set-cookie']
    assert r.headers['strict-transport-security']=='max-age=31536000'

def test_idle_sessions_expire_but_active_reads_refresh_last_seen(secured):
    c=client();signup(c)
    with secured.begin() as db:db.query(LoginSession).update({'last_seen_at':(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat()})
    assert c.get('/api/news').status_code==200
    with secured() as db:assert db.query(LoginSession).one().last_seen_at>(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
    with secured.begin() as db:db.query(LoginSession).update({'last_seen_at':(datetime.now(timezone.utc)-timedelta(minutes=31)).isoformat()})
    assert c.get('/api/news').status_code==401

def test_registration_is_local_by_default_and_remote_cannot_claim_owner(secured,monkeypatch):
    remote=TestClient(main.app,client=('198.51.100.4',50000))
    response=remote.post('/api/auth/register',headers=csrf(remote),json={'name':'Remote','email':'remote@example.test','password':'Private test password 123'})
    assert response.status_code==403
    monkeypatch.setattr(accounts,'ALLOW_REMOTE_REGISTRATION',True)
    response=remote.post('/api/auth/register',headers=csrf(remote),json={'name':'Remote','email':'remote@example.test','password':'Private test password 123'})
    assert response.status_code==403
    signup(client())
    response=remote.post('/api/auth/register',headers=csrf(remote),json={'name':'Remote','email':'remote@example.test','password':'Private test password 123'})
    assert response.status_code==200 and response.json()['user']['id']!='local'

def test_other_accounts_cannot_trigger_global_source_refreshes(secured):
    signup(client());other=client();signup(other,'other@example.test')
    assert other.post('/api/news/refresh',headers=csrf(other),json={}).status_code==403
    assert other.post('/api/youtube/refresh',headers=csrf(other),json={'company':'all'}).status_code==403

def test_rate_buckets_are_bounded_and_report_retry_after(secured):
    buckets=security.RateBuckets(capacity=3)
    for n in range(10):assert buckets.allow(str(n),1)
    assert len(buckets.rows)==3 and not buckets.allow('9',1)
    c=client()
    for _ in range(30):assert c.get('/api/session').status_code==200
    blocked=c.get('/api/session');assert blocked.status_code==429 and blocked.headers['Retry-After']=='60'

def test_owner_cannot_read_audio_granted_only_to_another_account(secured,tmp_path,monkeypatch):
    owner=client();signup(owner);other=client();user=signup(other,'other@example.test')
    audio_id='a'*64;folder=tmp_path/'audio';folder.mkdir();(folder/(audio_id+'.mp3')).write_bytes(b'private test audio')
    monkeypatch.setattr(main,'DATA',tmp_path)
    with secured.begin() as db:db.add(AudioGrant(user_id=user['id'],audio_id=audio_id))
    assert owner.get('/api/audio/'+audio_id).status_code==404
    assert other.get('/api/audio/'+audio_id).status_code==200

def test_active_sessions_are_capped_per_account(secured):
    owner=client();signup(owner)
    for _ in range(5):
        c=client();assert c.post('/api/auth/login',headers=csrf(c),json={'email':'reader@example.test','password':'Private test password 123'}).status_code==200
    with secured() as db:assert db.query(LoginSession).count()==5
    assert owner.get('/api/news').status_code==401


@pytest.mark.parametrize('url',['https://127.0.0.1/private','https://169.254.169.254/latest/meta-data','https://evil.example/news','https://openai.com.evil.example/news','https://user:pass@openai.com/news','http://openai.com/news','https://openai.com:8443/news'])
def test_source_requests_and_redirect_targets_cannot_escape_the_allowlist(url):
    import httpx
    with pytest.raises(httpx.RequestError):asyncio.run(ingestion.source_request_guard(httpx.Request('GET',url)))


def test_known_source_request_still_allowed():
    import httpx
    asyncio.run(ingestion.source_request_guard(httpx.Request('GET','https://openai.com/news/rss.xml')))


def test_csrf_cannot_be_bypassed_with_an_admin_bearer_in_account_mode(secured,monkeypatch):
    c=client();signup(c);monkeypatch.setattr(main,'ADMIN_TOKEN','test-only-admin-token')
    response=c.put('/api/auth/profile',headers={'Authorization':'Bearer test-only-admin-token'},json={'name':'Unprotected change'})
    assert response.status_code==403


def test_account_throttle_is_bounded_and_limits_identity_across_addresses(secured):
    for n in range(30):
        request=Request({'type':'http','client':('198.51.100.'+str(n),1),'headers':[]})
        accounts.throttle(request,'same@example.test')
    request=Request({'type':'http','client':('203.0.113.1',1),'headers':[]})
    with pytest.raises(HTTPException) as denied:accounts.throttle(request,'same@example.test')
    assert denied.value.status_code==429 and len(accounts.attempts)<=8192


def test_unhandled_errors_have_safe_responses_and_do_not_log_the_secret(caplog):
    from fastapi import FastAPI
    app=FastAPI()
    @app.get('/api/failure')
    def failure():raise RuntimeError('A simulated server credential must never be logged')
    app.add_middleware(security.SecurityEnvelope,origin_provider=lambda:'http://testserver')
    result=TestClient(app,raise_server_exceptions=False).get('/api/failure')
    assert result.status_code==500 and 'credential' not in result.text
    assert 'credential' not in caplog.text and result.headers['x-frame-options']=='DENY'


def test_malformed_authorities_and_excessive_urls_are_rejected(secured):
    c=client()
    for host in ['user@testserver','testserver:bad','testserver/other','testserver:99999']:
        assert c.get('/api/auth/session',headers={'Host':host}).status_code==400
    assert c.get('/api/news?q='+('x'*8193)).status_code==414
    assert c.post('/api/auth/login',content=b'',headers={'Content-Length':'9'*5000}).status_code==400
