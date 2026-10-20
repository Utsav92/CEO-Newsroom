"""Bounded request handling, browser policy and session-bound CSRF protection."""
import asyncio,hashlib,hmac,ipaddress,secrets,threading,time,uuid,logging
from collections import OrderedDict,deque
from urllib.parse import urlsplit
from starlette.datastructures import Headers,MutableHeaders
from starlette.responses import JSONResponse
from .config import CSRF_KEY,SERVERLESS

CSRF_SECRET=CSRF_KEY.encode() if CSRF_KEY else secrets.token_bytes(32)

class RateBuckets:
    def __init__(self,capacity=8192):self.capacity=capacity;self.rows=OrderedDict();self.lock=threading.Lock()
    def clear(self):
        with self.lock:self.rows.clear()
    def allow(self,key,limit,seconds=60):
        if SERVERLESS:
            from .serverless import shared_rate_limit
            return shared_rate_limit(key,limit,seconds)
        now=time.monotonic()
        with self.lock:
            queue=self.rows.pop(key,deque())
            while queue and now-queue[0]>=seconds:queue.popleft()
            accepted=len(queue)<limit
            if accepted:queue.append(now)
            self.rows[key]=queue
            while len(self.rows)>self.capacity:self.rows.popitem(last=False)
            return accepted

request_limits=RateBuckets()

def loopback(host):
    try:return ipaddress.ip_address(host).is_loopback
    except ValueError:return False

def csrf_token(auth_cookie=''):
    stamp=str(int(time.time()));nonce=secrets.token_urlsafe(24)
    data=stamp+'.'+nonce+'.'+hashlib.sha256(auth_cookie.encode()).hexdigest()
    return stamp+'.'+nonce+'.'+hmac.new(CSRF_SECRET,data.encode(),hashlib.sha256).hexdigest()

def valid_csrf(token,auth_cookie=''):
    if not token or len(token)>180:return False
    try:
        stamp,nonce,signature=token.split('.')
        if not nonce or not 0<=time.time()-int(stamp)<=86400:return False
        data=stamp+'.'+nonce+'.'+hashlib.sha256(auth_cookie.encode()).hexdigest()
        return hmac.compare_digest(signature,hmac.new(CSRF_SECRET,data.encode(),hashlib.sha256).hexdigest())
    except (ValueError,TypeError):return False

class SecurityEnvelope:
    def __init__(self,app,origin_provider,extra_origin_provider=lambda:''):
        self.app=app;self.origin_provider=origin_provider;self.extra_origin_provider=extra_origin_provider
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        headers=Headers(scope=scope);path=scope.get('path','');method=scope['method'];secure=scope.get('scheme')=='https'
        request_id=uuid.uuid4().hex;started=False
        async def secured_send(message):
            nonlocal started
            if message['type']=='http.response.start':
                started=True;h=MutableHeaders(scope=message)
                h['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' https: data:; font-src 'self'; connect-src 'self'; media-src 'self' blob:; frame-src https://www.youtube.com https://www.youtube-nocookie.com; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'"
                h['X-Frame-Options']='DENY';h['X-Content-Type-Options']='nosniff'
                h['Referrer-Policy']='strict-origin-when-cross-origin';h['Cross-Origin-Opener-Policy']='same-origin'
                h['Cross-Origin-Resource-Policy']='same-origin';h['Permissions-Policy']='camera=(), microphone=(), geolocation=(), usb=(), payment=()'
                h['X-Request-ID']=request_id
                if path.startswith('/api/') or path=='/':h['Cache-Control']='no-store'
                if secure:h['Strict-Transport-Security']='max-age=31536000'
            await send(message)
        async def reject(status,detail):
            extra={'Retry-After':'60'} if status==429 else None
            await JSONResponse({'detail':detail},status_code=status,headers=extra)(scope,receive,secured_send)
        try:
            origin=urlsplit(self.origin_provider())
            if len(scope.get('query_string',b''))>8192 or len(path)>2048:return await reject(414,'Request URL is too long.')
            try:
                authority=urlsplit('http://'+headers.get('host',''));host=authority.hostname
                if authority.username or authority.password or authority.path or authority.query or authority.fragment or authority.port is not None and not 0<authority.port<=65535:
                    return await reject(400,'Invalid host header.')
            except ValueError:return await reject(400,'Invalid host header.')
            extra=urlsplit(self.extra_origin_provider()).hostname
            if host not in ('localhost','127.0.0.1','::1',origin.hostname,extra):
                return await reject(403,'Use the configured newsroom address.')
            if not secure and host not in ('localhost','127.0.0.1','::1','testserver'):
                return await reject(403,'HTTPS is required for remote access.')
            if path.startswith('/api/'):
                ip=(scope.get('client') or ('unknown',0))[0]
                if headers.get('sec-fetch-site')=='cross-site' and path!='/api/billing/webhook':
                    return await reject(403,'Cross-site API request rejected.')
                if not request_limits.allow(('api',ip),180):return await reject(429,'Too many requests. Try again shortly.')
                if method not in ('GET','HEAD','OPTIONS') and not request_limits.allow(('write',ip),60):
                    return await reject(429,'Too many changes. Try again shortly.')
                if path=='/api/session' and not request_limits.allow(('csrf',ip),30):
                    return await reject(429,'Too many session requests. Try again shortly.')
                if method not in ('GET','HEAD','OPTIONS'):
                    limit=1_000_000 if path=='/api/billing/webhook' else 131_072
                    length=headers.get('content-length')
                    if length is not None and (len(length)>12 or not length.isascii() or not length.isdigit()):return await reject(400,'Invalid content length.')
                    if length and int(length)>limit:return await reject(413,'Request body is too large.')
                    if length is not None and 'transfer-encoding' in headers:return await reject(400,'Ambiguous request framing.')
                    async def read_body():
                        chunks=[];size=0
                        while True:
                            message=await receive()
                            if message['type']=='http.disconnect':return None
                            chunk=message.get('body',b'');size+=len(chunk)
                            if size>limit:raise OverflowError()
                            chunks.append(chunk)
                            if not message.get('more_body'):return b''.join(chunks)
                    try:body=await asyncio.wait_for(read_body(),timeout=15)
                    except OverflowError:return await reject(413,'Request body is too large.')
                    except asyncio.TimeoutError:return await reject(408,'Request body timed out.')
                    if body is None:return
                    if length is not None and int(length)!=len(body):return await reject(400,'Content length does not match the request.')
                    sent=False
                    async def replay():
                        nonlocal sent
                        if not sent:sent=True;return {'type':'http.request','body':body,'more_body':False}
                        return await receive()
                    return await self.app(scope,replay,secured_send)
            return await self.app(scope,receive,secured_send)
        except Exception as exc:
            logging.getLogger('newsroom.security').error('Request %s failed (%s)',request_id,type(exc).__name__)
            if started:raise
            return await reject(500,'The request could not be completed. Reference: '+request_id)
