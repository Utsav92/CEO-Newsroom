import asyncio,hashlib,hmac,json,time
import pytest
from fastapi.testclient import TestClient as FastAPIClient
def TestClient(*args,**kwargs):
    kwargs.setdefault('client',('127.0.0.1',50000))
    return FastAPIClient(*args,**kwargs)
from app import main,accounts,billing,services,ai,chat_history
from app.database import Account,LoginSession,Membership,PaymentOrder,ChatMessage,ChatSession
from app.account_context import current_user,current_language

@pytest.fixture
def auth(db,monkeypatch):
    monkeypatch.setattr(main,'AUTH_REQUIRED',True);monkeypatch.setattr(accounts,'SCRYPT_N',1024)
    monkeypatch.setattr(billing,'STRIPE_KEY','');monkeypatch.setattr(billing,'STRIPE_WEBHOOK_SECRET','')
    return db

def csrf(client):return {'X-Newsroom-Token':client.get('/api/session').json()['token']}
def signup(client,email='owner@example.test'):
    r=client.post('/api/auth/register',headers=csrf(client),json={'name':'Reader','email':email,'password':'A test passphrase 987','language':'en'})
    assert r.status_code==200,r.text
    return r.json()['user']

def test_real_registration_preserves_owner_history_and_passwords_are_not_plaintext(auth):
    old=services.save_chat_result('Existing history',None,{'messages':[{'presenter':'newsroom','text':'Existing answer','citations':[]}]})
    client=TestClient(main.app)
    assert client.get('/api/news').status_code==401
    assert client.get('/api/auth/session').json()['first_run']
    user=signup(client)
    assert user['id']=='local' and client.get('/api/news').status_code==200
    assert client.get('/api/chat/sessions/'+old['session_id']).status_code==200
    with auth() as db:
        a=db.get(Account,'local');assert a.password_hash.startswith('scrypt$') and 'passphrase' not in a.password_hash
        raw=client.cookies.get('newsroom_auth');stored=db.query(LoginSession).one().token_hash
        assert stored==hashlib.sha256(raw.encode()).hexdigest() and stored!=raw
    assert 'password' not in json.dumps(user)

def test_logout_revokes_cookie_and_private_routes(auth):
    client=TestClient(main.app);signup(client);raw=client.cookies.get('newsroom_auth')
    response=client.post('/api/auth/logout',headers=csrf(client),json={});assert response.status_code==200
    assert client.get('/api/news').status_code==401
    client.cookies.set('newsroom_auth',raw,domain='testserver.local',path='/')
    assert client.get('/api/news').status_code==401
    response=client.post('/api/auth/login',headers=csrf(client),json={'email':'owner@example.test','password':'A test passphrase 987'})
    assert response.status_code==200 and client.cookies.get('newsroom_auth')!=raw
    assert 'HttpOnly' in response.headers['set-cookie']

def test_accounts_cannot_read_or_continue_another_accounts_conversations(auth,monkeypatch):
    owner=TestClient(main.app);signup(owner)
    old=services.save_chat_result('Private owner chat',None,{'messages':[{'presenter':'newsroom','text':'Private answer','citations':[]}]})
    other=TestClient(main.app);second=signup(other,'other@example.test')
    assert second['id']!='local'
    assert other.get('/api/chat/sessions').json()['sessions']==[]
    assert other.get('/api/chat/sessions/'+old['session_id']).status_code==404
    assert other.get('/api/chat/history/'+old['session_id']).status_code==404
    assert other.post('/api/chat',headers=csrf(other),json={'question':'Continue','session_id':old['session_id']}).status_code==404
    owner.put('/api/preferences',headers=csrf(owner),json={'saved':['owner-story']})
    assert other.get('/api/preferences').json()['saved']==[]

def test_expiry_csrf_and_bad_auth_are_enforced(auth):
    client=TestClient(main.app)
    assert client.post('/api/auth/register',json={'name':'Owner','email':'owner@example.test','password':'A test passphrase 987'}).status_code==403
    signup(client)
    assert client.post('/api/auth/logout',headers={**csrf(client),'Origin':'https://attacker.example'},json={}).status_code==403
    with auth.begin() as db:db.query(LoginSession).update({'expires_at':'2000-01-01T00:00:00+00:00'})
    assert client.get('/api/news').status_code==401
    response=client.post('/api/auth/login',headers=csrf(client),json={'email':'owner@example.test','password':'wrong'})
    assert response.status_code==401 and response.json()['detail']=='Email or password is incorrect.'

def test_password_validation_does_not_echo_secrets_and_login_is_throttled(auth):
    client=TestClient(main.app);secret='password-secret-'+('x'*150)
    r=client.post('/api/auth/register',headers=csrf(client),json={'name':'Reader','email':'reader@example.test','password':secret})
    assert r.status_code==422 and secret not in r.text
    accounts.attempts.clear()
    for _ in range(6):assert client.post('/api/auth/login',headers=csrf(client),json={'email':'unknown@example.test','password':'bad'}).status_code==401
    assert client.post('/api/auth/login',headers=csrf(client),json={'email':'unknown@example.test','password':'bad'}).status_code==429

def test_language_is_saved_and_drives_the_answer_prompt(auth,monkeypatch):
    client=TestClient(main.app);signup(client)
    assert client.put('/api/auth/language',headers=csrf(client),json={'language':'hi'}).json()['user']['language']=='hi'
    assert client.get('/api/auth/session').json()['user']['language']=='hi'
    assert client.put('/api/auth/language',headers=csrf(client),json={'language':'not-a-language'}).status_code==422
    calls=[]
    async def api(path,body):
        calls.append(body);return {'status':'completed','output':[{'content':[{'type':'output_text','text':'{}'}]}]}
    monkeypatch.setattr(ai,'api',api);token=current_language.set('hi')
    try:asyncio.run(ai.structured('Explain',{},ai.object_schema({}),'news_answer'))
    finally:current_language.reset(token)
    assert 'Hindi' in calls[0]['instructions']


def test_profile_changes_only_the_signed_in_accounts_name(auth):
    owner=TestClient(main.app);signup(owner)
    other=TestClient(main.app);signup(other,'other@example.test')
    changed=owner.put('/api/auth/profile',headers=csrf(owner),json={'name':'  Updated Reader  '})
    assert changed.status_code==200 and changed.json()['user']['name']=='Updated Reader'
    assert other.get('/api/auth/session').json()['user']['name']=='Reader'
    assert owner.put('/api/auth/profile',headers=csrf(owner),json={'name':'   '}).status_code==422


def test_password_change_rotates_current_session_and_revokes_other_sessions(auth):
    owner=TestClient(main.app);signup(owner);old_token=owner.cookies.get('newsroom_auth')
    other=TestClient(main.app)
    assert other.post('/api/auth/login',headers=csrf(other),json={'email':'owner@example.test','password':'A test passphrase 987'}).status_code==200
    body={'current_password':'wrong','new_password':'New secure passphrase 456'}
    assert owner.post('/api/auth/password',headers=csrf(owner),json=body).status_code==400
    assert other.get('/api/news').status_code==200
    body['current_password']='A test passphrase 987'
    response=owner.post('/api/auth/password',headers=csrf(owner),json=body)
    assert response.status_code==200 and response.json()['other_sessions_revoked']
    assert owner.cookies.get('newsroom_auth')!=old_token
    assert owner.get('/api/news').status_code==200 and other.get('/api/news').status_code==401
    assert other.post('/api/auth/login',headers=csrf(other),json={'email':'owner@example.test','password':'A test passphrase 987'}).status_code==401
    assert other.post('/api/auth/login',headers=csrf(other),json={'email':'owner@example.test','password':'New secure passphrase 456'}).status_code==200


def test_password_validation_redacts_both_values_and_rejects_reuse(auth):
    client=TestClient(main.app);signup(client)
    response=client.post('/api/auth/password',headers=csrf(client),json={'current_password':'SECRET-CURRENT','new_password':'tiny'})
    assert response.status_code==422 and 'SECRET-CURRENT' not in response.text and 'tiny' not in response.text
    response=client.post('/api/auth/password',headers=csrf(client),json={'current_password':'A test passphrase 987','new_password':'A test passphrase 987'})
    assert response.status_code==422


def test_stale_password_verification_cannot_create_a_session_after_password_changes(auth,monkeypatch):
    client=TestClient(main.app);signup(client)
    original=accounts.verify_password;replacement=accounts.password_hash('Changed during sign-in 123')
    def concurrent_change(password,stored):
        valid=original(password,stored)
        with auth.begin() as db:db.get(Account,'local').password_hash=replacement
        return valid
    monkeypatch.setattr(accounts,'verify_password',concurrent_change)
    other=TestClient(main.app)
    result=other.post('/api/auth/login',headers=csrf(other),json={'email':'owner@example.test','password':'A test passphrase 987'})
    assert result.status_code==409 and not other.cookies.get('newsroom_auth')

def test_prices_and_disconnected_payments_cannot_activate_membership(auth):
    client=TestClient(main.app);signup(client)
    data=client.get('/api/billing').json()
    assert [p['amount_cents'] for p in data['plans']]==[200,300,500]
    assert all(p['interval']=='month' and p['currency']=='usd' for p in data['plans'])
    assert len(data['methods'])==7 and not data['configured']
    r=client.post('/api/billing/checkout',headers=csrf(client),json={'plan':'gold','method':'credit_card'})
    assert r.status_code==503
    assert client.get('/api/billing').json()['membership']['status']=='inactive'


@pytest.mark.parametrize('prefix',['sk_test_','rk_test_'])
def test_standard_and_restricted_test_keys_are_test_mode(auth,monkeypatch,prefix):
    monkeypatch.setattr(billing,'STRIPE_KEY',prefix+'fixture')
    monkeypatch.setattr(billing,'STRIPE_WEBHOOK_SECRET','whsec_fixture')
    assert billing.configured() and billing.test_mode()


@pytest.mark.parametrize('prefix',['sk_live_','rk_live_'])
def test_live_keys_require_https_and_are_never_test_mode(auth,monkeypatch,prefix):
    monkeypatch.setattr(billing,'STRIPE_KEY',prefix+'fixture')
    monkeypatch.setattr(billing,'STRIPE_WEBHOOK_SECRET','whsec_fixture')
    monkeypatch.setattr(billing,'PUBLIC_APP_URL','http://127.0.0.1:8788')
    assert not billing.configured() and not billing.test_mode()
    monkeypatch.setattr(billing,'PUBLIC_APP_URL','https://newsroom.example.test')
    assert billing.configured() and not billing.test_mode()


def test_a_publishable_key_cannot_enable_checkout(auth,monkeypatch):
    monkeypatch.setattr(billing,'STRIPE_KEY','pk_test_fixture')
    monkeypatch.setattr(billing,'STRIPE_WEBHOOK_SECRET','whsec_fixture')
    assert not billing.configured()

@pytest.fixture
def provider(auth,monkeypatch):
    monkeypatch.setattr(billing,'STRIPE_KEY','sk_test_fixture');monkeypatch.setattr(billing,'STRIPE_WEBHOOK_SECRET','whsec_fixture')
    calls=[];paid={'value':False}
    async def stripe(path,data=None,method='POST',idempotency=None):
        calls.append((path,data,method,idempotency))
        if path=='customers':return {'id':'cus_fixture'}
        if path=='checkout/sessions':return {'id':'cs_test_fixture','url':'https://checkout.stripe.com/c/pay/cs_test_fixture'}
        if path=='prices':return {'id':'price_fixture'}
        if path=='subscriptions':return {'id':'sub_fixture','latest_invoice':{'id':'in_fixture','status':'open','hosted_invoice_url':'https://invoice.stripe.com/i/fixture'}}
        with auth() as db:order=db.query(PaymentOrder).first();oid=order.id;user=order.user_id
        if path=='checkout/sessions/cs_test_fixture':return {'client_reference_id':user,'customer':'cus_fixture','metadata':{'order_id':oid},'payment_status':'paid' if paid['value'] else 'unpaid','subscription':'sub_fixture','status':'complete' if paid['value'] else 'open'}
        if path=='subscriptions/sub_fixture':return {'id':'sub_fixture','customer':'cus_fixture','metadata':{'user_id':user},'status':'active','latest_invoice':{'status':'paid' if paid['value'] else 'open'},'items':{'data':[{'price':{'unit_amount':300,'currency':'usd','recurring':{'interval':'month'}}}]}}
        if path=='billing_portal/sessions':return {'url':'https://billing.stripe.com/p/session/fixture'}
        raise AssertionError(path)
    monkeypatch.setattr(billing,'stripe',stripe)
    return calls,paid

def test_checkout_uses_server_price_and_never_activates_from_an_unpaid_return(auth,provider):
    calls,paid=provider;client=TestClient(main.app);signup(client)
    created=client.post('/api/billing/checkout',headers=csrf(client),json={'plan':'gold','method':'google_pay','amount':1})
    assert created.status_code==200
    form=next(c[1] for c in calls if c[0]=='checkout/sessions')
    assert form['line_items[0][price_data][unit_amount]']=='300' and form['mode']=='subscription'
    assert client.post('/api/billing/sync',headers=csrf(client),json={}).json()['membership']['status']=='inactive'
    paid['value']=True
    assert client.post('/api/billing/sync',headers=csrf(client),json={}).json()['membership']=={'plan':'gold','status':'active','can_manage':True}
    assert client.post('/api/billing/checkout',headers=csrf(client),json={'plan':'silver','method':'credit_card'}).status_code==409

def test_bank_transfer_creates_an_invoice_and_waits_for_payment(auth,provider):
    calls,paid=provider;client=TestClient(main.app);signup(client)
    r=client.post('/api/billing/checkout',headers=csrf(client),json={'plan':'gold','method':'bank_transfer'})
    assert r.status_code==200 and r.json()['url'].startswith('https://invoice.stripe.com/')
    form=next(c[1] for c in calls if c[0]=='subscriptions')
    assert form['collection_method']=='send_invoice' and form['payment_settings[payment_method_types][0]']=='customer_balance'
    assert client.post('/api/billing/sync',headers=csrf(client),json={}).json()['membership']['status']=='pending'
    paid['value']=True
    assert client.post('/api/billing/sync',headers=csrf(client),json={}).json()['membership']['status']=='active'

def test_qr_contains_only_a_real_owned_payment_page(auth,provider):
    client=TestClient(main.app);signup(client)
    order=client.post('/api/billing/checkout',headers=csrf(client),json={'plan':'gold','method':'qr_code'}).json()
    qr=client.get('/api/billing/qr/'+order['id'])
    assert qr.status_code==200 and qr.content.startswith(b'\x89PNG')
    other=TestClient(main.app);signup(other,'second@example.test')
    assert other.get('/api/billing/qr/'+order['id']).status_code==404


def test_retry_after_uncertain_provider_failure_keeps_order_and_idempotency(auth,provider,monkeypatch):
    calls,_=provider;original=billing.stripe;attempts=[]
    async def flaky(path,data=None,method='POST',idempotency=None):
        if path=='checkout/sessions':
            attempts.append((dict(data),idempotency))
            if len(attempts)==1:raise billing.BillingUnavailable('Temporary test outage')
        return await original(path,data,method,idempotency)
    monkeypatch.setattr(billing,'stripe',flaky)
    client=TestClient(main.app);signup(client)
    body={'plan':'gold','method':'credit_card'}
    assert client.post('/api/billing/checkout',headers=csrf(client),json=body).status_code==503
    assert client.post('/api/billing/checkout',headers=csrf(client),json=body).status_code==200
    assert attempts[0]==attempts[1]
    with auth() as db:assert db.query(PaymentOrder).count()==1


def test_wrong_price_and_stale_webhook_cannot_activate_membership(auth,provider,monkeypatch):
    _,paid=provider;client=TestClient(main.app);signup(client)
    client.post('/api/billing/checkout',headers=csrf(client),json={'plan':'gold','method':'credit_card'})
    original=billing.stripe;paid['value']=True
    async def wrong_price(path,data=None,method='POST',idempotency=None):
        result=await original(path,data,method,idempotency)
        if path=='subscriptions/sub_fixture':result['items']['data'][0]['price']['currency']='eur'
        return result
    monkeypatch.setattr(billing,'stripe',wrong_price)
    assert client.post('/api/billing/sync',headers=csrf(client),json={}).status_code==503
    assert client.get('/api/billing').json()['membership']['status']=='inactive'
    raw=b'{"id":"evt_old"}';stamp=str(int(time.time()-600))
    signature=hmac.new(b'whsec_fixture',stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    assert client.post('/api/billing/webhook',content=raw,headers={'Stripe-Signature':'t='+stamp+',v1='+signature}).status_code==400
    assert not billing.safe_url('https://checkout.stripe.com.evil.example/pay')

def test_webhook_requires_valid_recent_signature_and_is_replay_safe(auth,provider):
    calls,paid=provider;client=TestClient(main.app);signup(client)
    client.post('/api/billing/checkout',headers=csrf(client),json={'plan':'gold','method':'credit_card'})
    raw=json.dumps({'id':'evt_fixture','type':'invoice.paid','data':{'object':{'customer':'cus_fixture'}}}).encode();stamp=str(int(time.time()))
    signature=hmac.new(b'whsec_fixture',stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    assert client.post('/api/billing/webhook',content=raw,headers={'Stripe-Signature':'bad'}).status_code==400
    paid['value']=True
    headers={'Stripe-Signature':'t='+stamp+',v1='+signature}
    assert client.post('/api/billing/webhook',content=raw,headers=headers).status_code==200
    count=len(calls)
    assert client.post('/api/billing/webhook',content=raw,headers=headers).status_code==200 and len(calls)==count
    assert client.get('/api/billing').json()['membership']['status']=='active'


def test_invoice_history_is_customer_scoped_paginated_and_strips_unsafe_links(auth,provider,monkeypatch):
    client=TestClient(main.app);signup(client)
    client.post('/api/billing/checkout',headers=csrf(client),json={'plan':'gold','method':'credit_card'})
    original=billing.stripe;queries=[]
    async def invoices(path,data=None,method='POST',idempotency=None):
        if path=='invoices':
            queries.append(data)
            return {'has_more':True,'data':[{'id':'in_history','customer':'cus_fixture','number':'QA-001','status':'paid','created':1792368000,'total':300,'amount_paid':300,'currency':'usd','hosted_invoice_url':'https://evil.example/invoice','invoice_pdf':'https://pay.stripe.com/invoice/fixture/pdf','customer_email':'private@example.test'}]}
        return await original(path,data,method,idempotency)
    monkeypatch.setattr(billing,'stripe',invoices)
    result=client.get('/api/billing/history').json()
    assert queries==[{'customer':'cus_fixture','limit':'10'}]
    assert result['invoices'][0]['url'] is None and result['invoices'][0]['pdf_url'].startswith('https://pay.stripe.com/')
    assert 'private@example.test' not in json.dumps(result) and result['next_cursor']=='in_history'
    assert result['orders'][0]['plan']=='gold'
    assert client.get('/api/billing/history?after=in_history').status_code==200 and queries[-1]['starting_after']=='in_history'
    assert client.get('/api/billing/history?after=../../bad').status_code==422
    other=TestClient(main.app);signup(other,'second@example.test')
    result=other.get('/api/billing/history').json()
    assert not result['orders'] and not result['invoices'] and len(queries)==2


def test_history_keeps_local_attempts_during_a_stripe_outage(auth,provider,monkeypatch):
    client=TestClient(main.app);signup(client)
    client.post('/api/billing/checkout',headers=csrf(client),json={'plan':'gold','method':'credit_card'})
    async def outage(*args,**kwargs):raise billing.BillingUnavailable('Stripe temporarily unavailable.')
    monkeypatch.setattr(billing,'stripe',outage)
    result=client.get('/api/billing/history').json()
    assert len(result['orders'])==1 and result['warning'] and not result['invoices']


def test_stop_and_resume_renewal_only_updates_an_owned_subscription(auth,provider,monkeypatch):
    _,paid=provider;client=TestClient(main.app);signup(client)
    client.post('/api/billing/checkout',headers=csrf(client),json={'plan':'gold','method':'credit_card'})
    paid['value']=True
    assert client.post('/api/billing/sync',headers=csrf(client),json={}).status_code==200
    original=billing.stripe;updates=[];cancel={'value':False}
    async def renewal(path,data=None,method='POST',idempotency=None):
        result=await original(path,None if path=='subscriptions/sub_fixture' else data,method,idempotency)
        if path=='subscriptions/sub_fixture':
            if method=='POST':updates.append(data);cancel['value']=data['cancel_at_period_end']=='true'
            result.update(cancel_at_period_end=cancel['value'],items={**result['items'],'data':[{**result['items']['data'][0],'current_period_end':1794960000}]})
        return result
    monkeypatch.setattr(billing,'stripe',renewal)
    result=client.post('/api/billing/renewal',headers=csrf(client),json={'renew':False})
    assert result.status_code==200 and result.json()['subscription']['cancel_at_period_end']
    assert result.json()['subscription']['period_end']==1794960000 and result.json()['membership']['status']=='active'
    result=client.post('/api/billing/renewal',headers=csrf(client),json={'renew':True})
    assert result.status_code==200 and not result.json()['subscription']['cancel_at_period_end']
    assert updates==[{'cancel_at_period_end':'true'},{'cancel_at_period_end':'false'}]
    other=TestClient(main.app);signup(other,'second@example.test')
    assert other.post('/api/billing/renewal',headers=csrf(other),json={'renew':False}).status_code==409
