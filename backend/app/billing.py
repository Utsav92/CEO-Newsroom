"""Stripe-hosted monthly payments; access is never activated by a return URL."""
import asyncio,hashlib,hmac,json,secrets,time,uuid,io,re
from urllib.parse import urlsplit
from datetime import datetime,timezone,timedelta
import httpx
from fastapi import HTTPException
from sqlalchemy import select
from .config import STRIPE_KEY,STRIPE_WEBHOOK_SECRET,PUBLIC_APP_URL
from .database import Session,Account,User,Membership,PaymentOrder,BillingEvent

PLANS={'silver':200,'gold':300,'platinum':500}
METHODS=['google_pay','apple_pay','credit_card','debit_card','mastercard','bank_transfer','qr_code']
locks={}

class BillingUnavailable(Exception):pass

def configured():
    supported=STRIPE_KEY.startswith(('sk_test_','rk_test_','sk_live_','rk_live_'))
    live=STRIPE_KEY.startswith(('sk_live_','rk_live_'))
    return bool(supported and STRIPE_WEBHOOK_SECRET and (not live or PUBLIC_APP_URL.startswith('https://')))

def test_mode():return STRIPE_KEY.startswith(('sk_test_','rk_test_'))

def safe_url(url):
    p=urlsplit(url or '')
    return bool(p.scheme=='https' and p.hostname in ('checkout.stripe.com','invoice.stripe.com','billing.stripe.com','pay.stripe.com') and not p.username and not p.password)

async def stripe(path,data=None,method='POST',idempotency=None):
    if not STRIPE_KEY:raise BillingUnavailable('Stripe is not connected yet. No payment has been taken.')
    headers={'Authorization':'Bearer '+STRIPE_KEY}
    if idempotency:headers['Idempotency-Key']=idempotency
    try:
        async with httpx.AsyncClient(timeout=35) as client:
            response=await client.request(method,'https://api.stripe.com/v1/'+path,headers=headers,data=data if method=='POST' else None,params=data if method=='GET' else None)
        if response.status_code>=400:raise BillingUnavailable('Stripe could not complete this request. Check the merchant configuration or try again. No membership was activated.')
        return response.json()
    except (httpx.HTTPError,ValueError):raise BillingUnavailable('Stripe could not be reached. Try again; your membership has not been changed.') from None

def membership(user):
    with Session() as db:
        m=db.get(Membership,user)
        order=db.get(PaymentOrder,m.pending_order) if m and m.pending_order else None
        return {'configured':configured(),'test_mode':test_mode(),'plans':[{'id':id,'name':id.title(),'amount_cents':amount,'currency':'usd','interval':'month'} for id,amount in PLANS.items()],
            'membership':{'plan':m.plan if m else 'none','status':m.status if m else 'inactive','can_manage':bool(m and m.customer_id)},'pending':{'id':order.id,'plan':order.plan,'method':order.method,'url':order.url,'status':order.status} if order and order.status in ('pending','creating') else None,
            'methods':METHODS,'note':'Wallet availability depends on your device and Stripe eligibility. Bank transfers use monthly Stripe invoices; access starts after payment is confirmed.'}

async def checkout(user,plan,method):
    if plan not in PLANS or method not in METHODS:raise HTTPException(422,'Choose a listed plan and payment option.')
    if not configured():raise BillingUnavailable('Stripe payments are not connected yet. Your plan selection is ready, but no payment has been taken.')
    async with locks.setdefault(user,asyncio.Lock()):
        with Session.begin() as db:
            account=db.get(Account,user);member=db.get(Membership,user,with_for_update=True)
            if not account:raise HTTPException(401,'Sign in to choose a plan.')
            if not member:member=Membership(user_id=user);db.add(member);db.flush()
            if member.status=='active':raise HTTPException(409,'You already have a membership. Use Manage subscription to change or cancel it.')
            old=db.get(PaymentOrder,member.pending_order) if member.pending_order else None
            if old and old.status in ('creating','pending'):
                if old.plan==plan and old.method==method and old.url:return {'id':old.id,'url':old.url,'method':old.method}
                if old.plan!=plan or old.method!=method:
                    raise HTTPException(409,'A payment is already pending. Continue that payment or use Manage subscription before starting another.')
                if datetime.now(timezone.utc)-datetime.fromisoformat(old.created_at)>timedelta(hours=23):
                    raise BillingUnavailable('This payment needs merchant reconciliation before retrying. Check Stripe for the pending request first.')
            customer=member.customer_id;email=account.email;name=db.get(User,user).name
            order=old if old and old.status in ('creating','pending') else PaymentOrder(id=str(uuid.uuid4()),user_id=user,plan=plan,method=method)
            db.add(order);db.flush();member.pending_order=order.id;oid=order.id
            # The complete request, including expiry, must stay identical on retries.
            expiry=str(int(datetime.fromisoformat(order.created_at).timestamp()+1800))
        try:
            if not customer:
                c=await stripe('customers',{'email':email,'name':name,'metadata[user_id]':user},idempotency='customer-'+user)
                customer=c['id']
                with Session.begin() as db:db.get(Membership,user).customer_id=customer
            if method=='bank_transfer':
                price=await stripe('prices',{'currency':'usd','unit_amount':str(PLANS[plan]),'recurring[interval]':'month','product_data[name]':'CEO Newsroom '+plan.title()},idempotency='price-'+oid)
                sub=await stripe('subscriptions',{'customer':customer,'items[0][price]':price['id'],'collection_method':'send_invoice','days_until_due':'7','payment_settings[payment_method_types][0]':'customer_balance','metadata[user_id]':user,'metadata[order_id]':oid,'expand[0]':'latest_invoice'},idempotency='subscription-'+oid)
                invoice=sub.get('latest_invoice')
                if isinstance(invoice,str):invoice=await stripe('invoices/'+invoice,method='GET')
                if invoice and invoice.get('status')=='draft':invoice=await stripe('invoices/'+invoice['id']+'/finalize',idempotency='finalize-'+oid)
                url=(invoice or {}).get('hosted_invoice_url');provider_id=sub['id']
            else:
                form={'mode':'subscription','customer':customer,'client_reference_id':user,'payment_method_types[0]':'card','line_items[0][price_data][currency]':'usd','line_items[0][price_data][unit_amount]':str(PLANS[plan]),'line_items[0][price_data][recurring][interval]':'month','line_items[0][price_data][product_data][name]':'CEO Newsroom '+plan.title(),'line_items[0][quantity]':'1','success_url':PUBLIC_APP_URL+'/?settings=pricing&payment=returned','cancel_url':PUBLIC_APP_URL+'/?settings=pricing&payment=cancelled','metadata[user_id]':user,'metadata[order_id]':oid,'subscription_data[metadata][user_id]':user,'subscription_data[metadata][order_id]':oid,'expires_at':str(int(time.time()+1800))}
                form['expires_at']=expiry
                session=await stripe('checkout/sessions',form,idempotency='checkout-'+oid);url=session.get('url');provider_id=session['id']
            if not safe_url(url):raise BillingUnavailable('Stripe did not return a valid payment page. Please try again from your membership settings.')
            with Session.begin() as db:
                row=db.get(PaymentOrder,oid);row.url=url;row.provider_id=provider_id;row.status='pending'
                if method=='bank_transfer':db.get(Membership,user).subscription_id=provider_id
            return {'id':oid,'url':url,'method':method}
        except Exception:
            # Keep indeterminate provider outcomes pending: do not create duplicate subscriptions on retry.
            with Session.begin() as db:
                row=db.get(PaymentOrder,oid)
                if row:row.status='pending'
            raise

async def synchronize(user):
    with Session() as db:
        member=db.get(Membership,user)
        if not member:return membership(user)
        order=db.get(PaymentOrder,member.pending_order) if member.pending_order else None
        sid=member.subscription_id;customer=member.customer_id
        if order:oid=order.id;provider=order.provider_id;method=order.method
    if order and order.status in ('creating','pending'):
        if not provider:raise BillingUnavailable('The payment is still being prepared. Please try checking again shortly.')
        if method!='bank_transfer':
            session=await stripe('checkout/sessions/'+provider,method='GET')
            if session.get('client_reference_id')!=user or session.get('customer')!=customer or session.get('metadata',{}).get('order_id')!=oid:raise BillingUnavailable('Payment ownership could not be verified.')
            if session.get('status')=='expired':
                with Session.begin() as db:db.get(PaymentOrder,oid).status='expired';db.get(Membership,user).pending_order=None
                return membership(user)
            if session.get('payment_status')!='paid':return membership(user)
            sid=session.get('subscription')
        else:sid=provider
    if not sid:return membership(user)
    sub=await stripe('subscriptions/'+sid,{'expand[0]':'latest_invoice'},method='GET')
    if sub.get('customer')!=customer or sub.get('metadata',{}).get('user_id')!=user:raise BillingUnavailable('Subscription ownership could not be verified.')
    items=sub.get('items',{}).get('data',[]);price=items[0].get('price',{}) if len(items)==1 else {}
    plan=next((id for id,cents in PLANS.items() if price.get('unit_amount')==cents),None)
    if not plan or price.get('currency')!='usd' or price.get('recurring',{}).get('interval')!='month' or price.get('recurring',{}).get('interval_count',1)!=1 or items[0].get('quantity',1)!=1 or (order and order.status in ('creating','pending') and order.plan!=plan):raise BillingUnavailable('The subscription price does not match a newsroom plan.')
    invoice=sub.get('latest_invoice')
    if isinstance(invoice,str):invoice=await stripe('invoices/'+invoice,method='GET')
    paid=bool(invoice and invoice.get('status')=='paid')
    status='active' if sub.get('status')=='active' and paid else 'cancelled' if sub.get('status') in ('canceled','incomplete_expired') else 'past_due' if sub.get('status') in ('past_due','unpaid') else 'pending'
    with Session.begin() as db:
        m=db.get(Membership,user);m.subscription_id=sid;m.status=status
        if status=='active':m.plan=plan
        if order and status in ('active','cancelled'):
            db.get(PaymentOrder,order.id).status='paid' if status=='active' else 'cancelled';m.pending_order=None
    return membership(user)

async def portal(user):
    with Session() as db:member=db.get(Membership,user);customer=member.customer_id if member else None
    if not customer:raise HTTPException(409,'Choose a plan before managing a subscription.')
    data=await stripe('billing_portal/sessions',{'customer':customer,'return_url':PUBLIC_APP_URL+'/?settings=pricing'})
    if not safe_url(data.get('url')):raise BillingUnavailable('Stripe did not return a valid subscription page.')
    return {'url':data['url']}


def subscription_summary(sub):
    items=sub.get('items',{}).get('data',[])
    end=sub.get('current_period_end') or (items[0].get('current_period_end') if items else None)
    return {'status':sub.get('status','unknown'),'cancel_at_period_end':bool(sub.get('cancel_at_period_end')),
        'period_end':end,'cancel_at':sub.get('cancel_at'),'collection_method':sub.get('collection_method')}


def verify_subscription(sub,user,customer):
    if sub.get('customer')!=customer or sub.get('metadata',{}).get('user_id')!=user:
        raise BillingUnavailable('Subscription ownership could not be verified.')


async def history(user,after=''):
    if after and not re.fullmatch(r'in_[A-Za-z0-9_]{1,180}',after):raise HTTPException(422,'Invalid invoice cursor.')
    with Session() as db:
        member=db.get(Membership,user);customer=member.customer_id if member else None;sid=member.subscription_id if member else None
        orders=db.scalars(select(PaymentOrder).where(PaymentOrder.user_id==user).order_by(PaymentOrder.created_at.desc()).limit(30)).all()
        attempts=[{'id':o.id,'plan':o.plan,'method':o.method,'status':o.status,'created_at':o.created_at,
            'amount_cents':PLANS.get(o.plan),'currency':'usd','url':o.url if safe_url(o.url) and o.status in ('pending','creating') else None} for o in orders]
    result={'orders':attempts,'invoices':[],'subscription':None,'next_cursor':None,'warning':'',
        'connected':configured(),'note':'Payment attempts are separate from invoices. A pending attempt does not mean money was received.'}
    if not configured() or not customer:return result
    try:
        if sid:
            sub=await stripe('subscriptions/'+sid,method='GET');verify_subscription(sub,user,customer)
            result['subscription']=subscription_summary(sub)
        params={'customer':customer,'limit':'10'}
        if after:params['starting_after']=after
        records=await stripe('invoices',params,method='GET')
        invoices=records.get('data',[])
        if any(i.get('customer')!=customer for i in invoices):raise BillingUnavailable('Invoice ownership could not be verified.')
        result['invoices']=[{'id':i['id'],'number':i.get('number'),'status':i.get('status','draft'),
            'created':i.get('created'),'due_date':i.get('due_date'),'amount_cents':i.get('total',0),
            'amount_paid':i.get('amount_paid',0),'currency':i.get('currency','usd'),
            'url':i.get('hosted_invoice_url') if safe_url(i.get('hosted_invoice_url')) else None,
            'pdf_url':i.get('invoice_pdf') if safe_url(i.get('invoice_pdf')) else None} for i in invoices]
        if records.get('has_more') and invoices:result['next_cursor']=invoices[-1]['id']
    except BillingUnavailable as exc:result['warning']=str(exc)
    return result


async def set_renewal(user,renew):
    if not configured():raise BillingUnavailable('Connect Stripe before managing subscription renewal.')
    async with locks.setdefault(user,asyncio.Lock()):
        with Session() as db:
            member=db.get(Membership,user);sid=member.subscription_id if member else None;customer=member.customer_id if member else None
        if not sid:raise HTTPException(409,'There is no subscription to manage.')
        sub=await stripe('subscriptions/'+sid,method='GET');verify_subscription(sub,user,customer)
        if sub.get('status') not in ('active','trialing','past_due','unpaid'):
            raise HTTPException(409,'This subscription cannot be renewed or cancelled here. Open Stripe management for help.')
        # Setting a boolean is repeatable; never delete the subscription or issue refunds here.
        updated=await stripe('subscriptions/'+sid,{'cancel_at_period_end':'false' if renew else 'true'})
        verify_subscription(updated,user,customer)
        if bool(updated.get('cancel_at_period_end'))==renew:
            raise BillingUnavailable('Stripe has not confirmed this renewal change. Refresh billing history before retrying.')
        await synchronize(user)
        return {'subscription':subscription_summary(updated),'membership':membership(user)['membership']}

def verify_event(body,signature):
    if not STRIPE_WEBHOOK_SECRET:raise HTTPException(503,'Stripe webhooks are not connected.')
    if len(body)>1_000_000:raise HTTPException(413,'Webhook too large.')
    try:
        parts=[p.split('=',1) for p in signature.split(',')];stamp=next(v for k,v in parts if k=='t')
        if abs(time.time()-int(stamp))>300:raise ValueError()
        expected=hmac.new(STRIPE_WEBHOOK_SECRET.encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
        if not any(k=='v1' and hmac.compare_digest(v,expected) for k,v in parts):raise ValueError()
        data=json.loads(body)
        if not isinstance(data,dict) or not isinstance(data.get('id'),str):raise ValueError()
        return data
    except (ValueError,StopIteration,TypeError):raise HTTPException(400,'Invalid Stripe signature.') from None

async def webhook(body,signature):
    event=verify_event(body,signature)
    with Session() as db:
        if db.get(BillingEvent,event['id']):return {'received':True}
    obj=event.get('data',{}).get('object',{});customer=obj.get('customer')
    with Session() as db:m=db.scalars(select(Membership).where(Membership.customer_id==customer)).first() if customer else None;user=m.user_id if m else None
    if user and event.get('type') in ('checkout.session.completed','checkout.session.async_payment_succeeded','invoice.paid','invoice.payment_failed','customer.subscription.updated','customer.subscription.deleted'):
        await synchronize(user)
    with Session.begin() as db:
        if not db.get(BillingEvent,event['id']):db.add(BillingEvent(id=event['id']))
    return {'received':True}

def qr_png(user,order_id):
    with Session() as db:
        order=db.get(PaymentOrder,order_id)
        if not order or order.user_id!=user or not safe_url(order.url):raise HTTPException(404,'Payment not found.')
        url=order.url
    import qrcode
    image=qrcode.make(url);out=io.BytesIO();image.save(out,format='PNG');return out.getvalue()
