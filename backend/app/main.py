import asyncio, json, secrets, hashlib, time, uuid
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from .config import ROOT, DATA, OPENAI_KEY, MODEL, TTS_MODEL, YOUTUBE_KEY, ADMIN_TOKEN
from .database import migrate, Session, Source, Article, Preference, ChatMessage, Briefing, IngestionJob, NotificationSetting
from .personas import PERSONAS, BY_COMPANY, BY_ID, TOPICS
from .services import preferences, articles, chat, generate_briefing, youtube, article_json
from .ingestion import ingest, REGISTRY
from .ai import AIUnavailable, api
from .rag import ArticleNotFound
from .chat_history import list_chats,load_chat
from .video_rag import VideoNotFound
from .config import GEMINI_KEY, VIDEO_MODEL
from .youtube import refresh_all as refresh_youtube, youtube as official_youtube, channel_state, OFFICIAL_CHANNELS, REFRESH_TIME
from . import accounts,billing
from .account_context import current_user,current_language,LANGUAGES
from .database import Account
from .database import AudioGrant
from .config import PUBLIC_APP_URL
from urllib.parse import urlsplit
from fastapi.exceptions import RequestValidationError
from .security import SecurityEnvelope,csrf_token,valid_csrf,request_limits
from .config import SERVERLESS,CSRF_KEY,CRON_SECRET,DEPLOYMENT_ORIGIN

AUTH_REQUIRED=True

scheduler=AsyncIOScheduler()
tasks=set()

async def scheduled_briefing(kind):
    generate_briefing(kind)

async def scheduled_youtube():
    return await refresh_youtube(key=YOUTUBE_KEY,tz=preferences()['timezone'])

def schedule_youtube():
    hour,minute=map(int,REFRESH_TIME.split(':'))
    scheduler.add_job(scheduled_youtube,CronTrigger(hour=hour,minute=minute,timezone=preferences()['timezone']),id='youtube-daily',replace_existing=True,max_instances=1,coalesce=True,misfire_grace_time=86400)

def schedule_briefings():
    p=preferences()
    for kind,clock in [('morning',p['briefing_time']),('evening',p['evening_time']),('weekly',p['briefing_time'])]:
        hour,minute=map(int,clock.split(':'))
        scheduler.add_job(scheduled_briefing,CronTrigger(hour=hour,minute=minute,timezone=p['timezone'],**({'day_of_week':'sun'} if kind=='weekly' else {})),id='briefing-'+kind,args=[kind],replace_existing=True,misfire_grace_time=3600)

async def initial_ingestion():
    await ingest()
    generate_briefing()

@asynccontextmanager
async def lifespan(app):
    if SERVERLESS:
        if len(CSRF_KEY)<64 or len(CRON_SECRET)<32:raise RuntimeError('Configure durable CSRF and cron secrets before deployment.')
        from .database import SchemaVersion
        with Session() as db:
            if not db.get(SchemaVersion,6):raise RuntimeError('Run the reviewed database migration before deployment.')
        yield
        return
    migrate(); schedule_briefings(); schedule_youtube()
    scheduler.add_job(ingest,'interval',minutes=30,id='ingestion',max_instances=1,coalesce=True)
    scheduler.start()
    with Session() as db: count=db.query(Article).count()
    if count==0:
        task=asyncio.create_task(initial_ingestion()); tasks.add(task); task.add_done_callback(tasks.discard)
    if YOUTUBE_KEY:
        task=asyncio.create_task(refresh_youtube(key=YOUTUBE_KEY,tz=preferences()['timezone'])); tasks.add(task); task.add_done_callback(tasks.discard)
    yield
    scheduler.shutdown(wait=False)
    for task in tasks: task.cancel()

app=FastAPI(title='CEO Newsroom',version='3.0.0',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)

@app.exception_handler(billing.BillingUnavailable)
async def payment_unavailable(request,exc):return JSONResponse(status_code=503,content={'detail':str(exc)})

@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    if request.url.path=='/api/auth/password':
        return JSONResponse(status_code=422,content={'detail':'Enter your current password and a new password with 12–128 characters.'})
    if request.url.path=='/api/auth/profile':
        return JSONResponse(status_code=422,content={'detail':'Enter a name with 1–80 characters.'})
    if request.url.path.startswith('/api/auth/'):
        return JSONResponse(status_code=422,content={'detail':'Check your name, email, and password. Passwords must contain 12–128 characters.'})
    from fastapi.exception_handlers import request_validation_exception_handler
    return await request_validation_exception_handler(request,exc)

@app.exception_handler(AIUnavailable)
async def unavailable(request,exc): return JSONResponse(status_code=503,content={'detail':str(exc)})

@app.exception_handler(ArticleNotFound)
async def missing_article(request,exc): return JSONResponse(status_code=404,content={'detail':str(exc)})

@app.exception_handler(VideoNotFound)
async def missing_video(request,exc): return JSONResponse(status_code=404,content={'detail':str(exc)})

@app.get('/api/video-understanding/status')
def video_understanding_status():
    return {'configured':bool(GEMINI_KEY),'model':VIDEO_MODEL,'capabilities':['speech','visuals','demonstrations','timestamped evidence'],'note':'A configured key still needs service access and quota. Public completed official uploads only.'}

@app.middleware('http')
async def local_security(request:Request,call_next):
    if request.url.path.startswith('/api/'):
        origin=request.headers.get('origin')
        # Local single-user app. Block cross-origin mutations and DNS rebinding.
        if request.url.hostname not in ('localhost','127.0.0.1','testserver',urlsplit(PUBLIC_APP_URL).hostname,urlsplit(DEPLOYMENT_ORIGIN).hostname):
            return JSONResponse(status_code=403,content={'detail':'Remote access requires NEWSROOM_ADMIN_TOKEN.'})
        if request.method not in ('GET','HEAD','OPTIONS'):
            if origin and origin not in ('http://localhost:5178','http://127.0.0.1:5178','http://localhost:8788','http://127.0.0.1:8788',PUBLIC_APP_URL,DEPLOYMENT_ORIGIN):
                return JSONResponse(status_code=403,content={'detail':'Cross-origin write rejected.'})
        if ADMIN_TOKEN and not AUTH_REQUIRED and request.url.path!='/api/billing/webhook' and request.headers.get('authorization')!='Bearer '+ADMIN_TOKEN:
            return JSONResponse(status_code=401,content={'detail':'A valid administrator token is required.'})
    public=request.url.path in ('/api/session','/api/auth/session','/api/auth/register','/api/auth/login','/api/auth/logout','/api/billing/webhook') or request.url.path.startswith('/api/cron/')
    user=accounts.session_user(request) if AUTH_REQUIRED and request.url.path.startswith('/api/') else None
    if AUTH_REQUIRED and request.url.path.startswith('/api/') and not public and not user:
        return JSONResponse(status_code=401,content={'detail':'Sign in to access your newsroom.'})
    if request.url.path in ('/api/chat','/api/audio'):
        identity=user['id'] if user else (request.client.host if request.client else 'local')
        if not request_limits.allow(('ai',identity),12):
            return JSONResponse(status_code=429,content={'detail':'Please wait a minute before making more AI requests.'},headers={'Retry-After':'60'})
    if request.url.path.startswith('/api/billing/') and request.url.path!='/api/billing/webhook' and user:
        if not request_limits.allow(('billing',user['id']),30):
            return JSONResponse(status_code=429,content={'detail':'Please wait before making more payment requests.'},headers={'Retry-After':'60'})
    owner=current_user.set(user['id'] if user else 'local');language=current_language.set(user['language'] if user else 'en')
    try:
        response=await call_next(request)
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control']='no-store'
        return response
    finally:current_user.reset(owner);current_language.reset(language)

def authorize(request:Request):
    if not AUTH_REQUIRED and ADMIN_TOKEN and secrets.compare_digest(request.headers.get('authorization',''),'Bearer '+ADMIN_TOKEN): return
    token=request.headers.get('x-newsroom-token','')
    if not token.isascii() or not valid_csrf(token,request.cookies.get('newsroom_auth','')) or not secrets.compare_digest(request.cookies.get('newsroom_session','').encode(),token.encode()):
        raise HTTPException(403,'Open the app to start an authorized local session.')

@app.get('/api/session')
def session(request:Request,response:Response):
    token=csrf_token(request.cookies.get('newsroom_auth',''))
    response.set_cookie('newsroom_session',token,httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=86400)
    return {'token':token}

class AccountInput(BaseModel):
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=1,max_length=128)

class RegisterInput(AccountInput):
    name:str=Field(min_length=1,max_length=80)
    language:str='en'
    @field_validator('name')
    @classmethod
    def real_name(cls,value):
        if not value.strip():raise ValueError('Enter your name')
        return value.strip()

@app.get('/api/auth/session')
def account_session(request:Request):
    with accounts.Session() as db:first=db.query(Account).count()==0
    return {'user':accounts.session_user(request),'first_run':first,'languages':LANGUAGES}

@app.post('/api/auth/register',dependencies=[Depends(authorize)])
def register_account(body:RegisterInput,request:Request,response:Response):return accounts.register(request,response,body.name,body.email,body.password,body.language)

@app.post('/api/auth/login',dependencies=[Depends(authorize)])
def login_account(body:AccountInput,request:Request,response:Response):return accounts.login(request,response,body.email,body.password)

@app.post('/api/auth/logout',dependencies=[Depends(authorize)])
def logout_account(request:Request,response:Response):return accounts.logout(request,response)

class ProfileInput(BaseModel):
    name:str=Field(min_length=1,max_length=80)
    @field_validator('name')
    @classmethod
    def valid_name(cls,value):
        if not value.strip():raise ValueError('Enter your name')
        return value.strip()

class PasswordInput(BaseModel):
    current_password:str=Field(min_length=1,max_length=128)
    new_password:str=Field(min_length=12,max_length=128)

@app.put('/api/auth/profile',dependencies=[Depends(authorize)])
def update_account(body:ProfileInput):return accounts.update_profile(current_user.get(),body.name)

@app.post('/api/auth/password',dependencies=[Depends(authorize)])
def update_password(body:PasswordInput,request:Request,response:Response):
    return accounts.change_password(current_user.get(),request,response,body.current_password,body.new_password)

class LanguageInput(BaseModel):
    language:str

@app.put('/api/auth/language',dependencies=[Depends(authorize)])
def account_language(body:LanguageInput):
    if body.language not in LANGUAGES:raise HTTPException(422,'Choose a supported language.')
    with accounts.Session.begin() as db:
        account=db.get(Account,current_user.get());account.language=body.language
        return {'user':accounts.profile(db,account)}

@app.get('/api/billing')
def get_billing():return billing.membership(current_user.get())

class CheckoutInput(BaseModel):
    plan:str
    method:str

@app.post('/api/billing/checkout',dependencies=[Depends(authorize)])
async def begin_checkout(body:CheckoutInput):return await billing.checkout(current_user.get(),body.plan,body.method)

@app.post('/api/billing/sync',dependencies=[Depends(authorize)])
async def sync_payment():return await billing.synchronize(current_user.get())

@app.post('/api/billing/portal',dependencies=[Depends(authorize)])
async def billing_portal():return await billing.portal(current_user.get())

@app.get('/api/billing/history')
async def billing_history(after:str=''):return await billing.history(current_user.get(),after)

class RenewalInput(BaseModel):
    renew:bool

@app.post('/api/billing/renewal',dependencies=[Depends(authorize)])
async def membership_renewal(body:RenewalInput):return await billing.set_renewal(current_user.get(),body.renew)

@app.get('/api/billing/qr/{order_id}')
def payment_qr(order_id:str):return Response(billing.qr_png(current_user.get(),order_id),media_type='image/png')

@app.post('/api/billing/webhook')
async def stripe_webhook(request:Request):
    body=bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body)>1_000_000:raise HTTPException(413,'Webhook too large.')
    return await billing.webhook(bytes(body),request.headers.get('stripe-signature',''))

@app.get('/api/ceos')
def ceos(): return [{'id':p['id'],'name':p['name'],'company':p['company'],'color':p['color'],'voice':p['voice'],'initials':p['initials'],'avatar':'/avatars/'+p['id']+'.webp','simulation':True,'aliases':p['terms']+[p['name']]} for p in PERSONAS]

@app.get('/api/news')
@app.get('/api/news/latest')
def news(company:str|None=None,topic:str|None=None,q:str='',period:str='all',saved:bool=False,limit:int=100):
    if period not in ('all','today','week','month'): raise HTTPException(422,'Unknown date period')
    from . import ingestion as news_ingestion
    return {'articles':articles(company,topic,q[:200],period,saved,min(max(limit,1),250)),'ingesting':news_ingestion.lock.locked()}

@app.get('/api/news/company/{company}')
def company_news(company:str):
    if company not in BY_COMPANY: raise HTTPException(404,'Unknown company')
    return {'articles':articles(company=company)}

@app.get('/api/news/article/{id}')
def article(id:str):
    with Session() as db:
        a=db.get(Article,id)
        if not a: raise HTTPException(404,'Article not found')
        return article_json(a)

@app.get('/api/sources')
def sources():
    with Session() as db:
        records={s.id:s for s in db.query(Source).all()}
        return [{'id':s['id'],'name':s['name'],'url':s['url'],'kind':s['kind'],'company':s.get('company'),'status':records[s['id']].status if s['id'] in records else 'not checked','detail':records[s['id']].detail if s['id'] in records else '', 'checked_at':records[s['id']].checked_at if s['id'] in records else None} for s in REGISTRY]

@app.post('/api/news/refresh',dependencies=[Depends(authorize)])
async def refresh():
    if AUTH_REQUIRED and current_user.get()!='local':raise HTTPException(403,'Only the newsroom owner can refresh shared sources.')
    return await ingest()

class ChatInput(BaseModel):
    question:str=Field(min_length=1,max_length=2000)
    session_id:str|None=Field(default=None,max_length=64)
    presenter:str|None=None
    period:str='all'
    article_id:str|None=Field(default=None,min_length=1,max_length=64)
    topic:str|None=Field(default=None,max_length=160)
    include_related:bool=True
    video_id:str|None=Field(default=None,pattern=r'^[A-Za-z0-9_-]{11}$')
    follow_up:bool=False
    @model_validator(mode='after')
    def single_source(self):
        if self.article_id and self.video_id:raise ValueError('Choose one article or video at a time')
        return self
    @field_validator('session_id')
    @classmethod
    def valid_session(cls,value):
        if value:
            try: uuid.UUID(value)
            except ValueError: raise ValueError('Invalid session ID')
        return value
    @field_validator('presenter')
    @classmethod
    def valid_presenter(cls,value):
        if value and value not in BY_ID: raise ValueError('Unknown presenter')
        return value
    @field_validator('period')
    @classmethod
    def valid_period(cls,value):
        if value not in ('all','today','week','month'): raise ValueError('Unknown date period')
        return value

@app.post('/api/chat',dependencies=[Depends(authorize)])
async def ask(body:ChatInput): return await chat(body.question,body.session_id,body.presenter,body.period,body.article_id,body.topic.strip() if body.topic else None,body.include_related,body.video_id,body.follow_up)

@app.get('/api/chat/history/{session_id}')
def history(session_id:str):
    result=load_chat(session_id)
    if result is None:raise HTTPException(404,'Conversation not found.')
    return result['messages']

@app.get('/api/chat/sessions')
def saved_chats(limit:int=100,offset:int=0):return {'sessions':list_chats(min(max(limit,1),250),max(offset,0))}

@app.get('/api/chat/sessions/{session_id}')
def saved_chat(session_id:uuid.UUID):
    result=load_chat(str(session_id))
    if result is None:raise HTTPException(404,'This conversation could not be found.')
    return result

@app.get('/api/briefings/today')
def briefing_today(kind:str='morning',company:str|None=None):
    if kind not in ('morning','evening','weekly'): raise HTTPException(422,'Invalid briefing type')
    if company and company not in BY_COMPANY: raise HTTPException(422,'Unknown company')
    return generate_briefing(kind,company)

@app.get('/api/briefings/history')
def briefing_history():
    with Session() as db: return [{**json.loads(b.payload),'id':b.id} for b in db.scalars(select(Briefing).order_by(Briefing.created_at.desc()).limit(30)).all()]

@app.get('/api/youtube/search')
async def videos(company:str='all',q:str=''):
    try: return await youtube(company,q)
    except ValueError as exc: raise HTTPException(422,str(exc))

@app.get('/api/youtube/status')
def youtube_status():
    job=scheduler.get_job('youtube-daily')
    return {'configured':bool(YOUTUBE_KEY),'daily_refresh_time':REFRESH_TIME,'timezone':preferences()['timezone'],'next_run':job.next_run_time.isoformat() if job and scheduler.running else None,'channels':[channel_state(c) for c in OFFICIAL_CHANNELS]}

class YouTubeRefreshInput(BaseModel):
    company:str='all'
    @field_validator('company')
    @classmethod
    def valid_company(cls,value):
        if value!='all' and value not in OFFICIAL_CHANNELS:raise ValueError('Unknown company')
        return value

@app.post('/api/youtube/refresh',dependencies=[Depends(authorize)])
async def youtube_refresh(body:YouTubeRefreshInput):
    if AUTH_REQUIRED and current_user.get()!='local':raise HTTPException(403,'Only the newsroom owner can refresh shared sources.')
    if SERVERLESS:
        from .serverless import run_exclusive
        return await run_exclusive('youtube-refresh',lambda:official_youtube(body.company,key=YOUTUBE_KEY,tz=preferences()['timezone'],force=True))
    return await official_youtube(body.company,key=YOUTUBE_KEY,tz=preferences()['timezone'],force=True)

class PrefInput(BaseModel):
    companies:list[str]=Field(default_factory=list,max_length=8)
    topics:list[str]=Field(default_factory=list,max_length=6)
    saved:list[str]=Field(default_factory=list,max_length=1000)
    personalization:bool=False
    timezone:str='Europe/London'
    briefing_time:str='08:00'
    evening_time:str='18:00'
    notifications:bool=False
    autoplay:bool=False
    voice:str='presenter'
    speed:float=Field(default=1,ge=.5,le=2)
    @field_validator('timezone')
    @classmethod
    def tz(cls,value):
        try: ZoneInfo(value)
        except ZoneInfoNotFoundError: raise ValueError('Unknown timezone')
        return value
    @field_validator('briefing_time','evening_time')
    @classmethod
    def clock(cls,value):
        try: datetime.strptime(value,'%H:%M')
        except ValueError: raise ValueError('Use HH:MM in 24-hour time')
        return value
    @field_validator('companies')
    @classmethod
    def companies_valid(cls,value):
        if any(c not in BY_COMPANY for c in value): raise ValueError('Unknown company')
        return list(dict.fromkeys(value))
    @field_validator('topics')
    @classmethod
    def topics_valid(cls,value):
        if any(c not in TOPICS for c in value): raise ValueError('Unknown topic')
        return list(dict.fromkeys(value))
    @field_validator('voice')
    @classmethod
    def voice_valid(cls,value):
        if value not in ['presenter']+[p['voice'] for p in PERSONAS]: raise ValueError('Unknown synthetic voice')
        return value

@app.get('/api/preferences')
def get_prefs(): return preferences()

@app.put('/api/preferences',dependencies=[Depends(authorize)])
def put_prefs(body:PrefInput):
    payload=body.model_dump()
    with Session.begin() as db:
        row=db.get(Preference,current_user.get())
        if row: row.payload=json.dumps(payload)
        else: db.add(Preference(id=current_user.get(),payload=json.dumps(payload)))
        setting=db.get(NotificationSetting,current_user.get())
        if setting: setting.enabled=int(body.notifications)
    if current_user.get()=='local' and not SERVERLESS:schedule_briefings(); schedule_youtube()
    return payload

class AudioInput(BaseModel):
    text:str=Field(min_length=1,max_length=3500)
    presenter:str='sam_altman'
    voice:str='presenter'

@app.post('/api/audio',dependencies=[Depends(authorize)])
async def audio(body:AudioInput):
    if body.presenter not in BY_ID: raise HTTPException(422,'Unknown presenter')
    voice=BY_ID[body.presenter]['voice'] if body.voice=='presenter' else body.voice
    if voice not in [p['voice'] for p in PERSONAS]: raise HTTPException(422,'Choose a generic synthetic presenter voice')
    id=hashlib.sha256((TTS_MODEL+voice+body.text).encode()).hexdigest()
    if SERVERLESS:
        from .serverless import cloud_audio
        await cloud_audio(id,lambda:api('audio/speech',{'model':TTS_MODEL,'voice':voice,'input':body.text,'response_format':'mp3','instructions':'Read as a neutral, clear news narrator. This is a generic synthetic voice. Do not impersonate a real person.'},binary=True))
        with Session.begin() as db:
            if not db.get(AudioGrant,(current_user.get(),id)):db.add(AudioGrant(user_id=current_user.get(),audio_id=id))
        return {'url':f'/api/audio/{id}','voice':voice,'disclosure':'AI-generated synthetic narration'}
    path=DATA/'audio'/f'{id}.mp3'; path.parent.mkdir(exist_ok=True)
    if not path.exists():
        data=await api('audio/speech',{'model':TTS_MODEL,'voice':voice,'input':body.text,'response_format':'mp3','instructions':'Read as a neutral, clear news narrator. This is a generic synthetic voice. Do not impersonate a real person.'},binary=True)
        path.write_bytes(data)
    with Session.begin() as db:
        if not db.get(AudioGrant,(current_user.get(),id)):db.add(AudioGrant(user_id=current_user.get(),audio_id=id))
    return {'url':f'/api/audio/{id}','voice':voice,'disclosure':'AI-generated synthetic narration'}

@app.get('/api/audio/{id}')
def audio_file(id:str):
    if len(id)!=64 or any(c not in '0123456789abcdef' for c in id): raise HTTPException(404)
    with Session() as db:
        if not db.get(AudioGrant,(current_user.get(),id)):raise HTTPException(404)
        if SERVERLESS:
            from .database import AudioCache
            cached=db.get(AudioCache,id)
            if not cached:raise HTTPException(404)
            return Response(cached.data,media_type='audio/mpeg')
    path=DATA/'audio'/f'{id}.mp3'
    if not path.exists(): raise HTTPException(404)
    return FileResponse(path,media_type='audio/mpeg')

@app.get('/api/health')
def health():
    with Session() as db:
        job=db.scalars(select(IngestionJob).order_by(IngestionJob.id.desc()).limit(1)).first()
        count=db.query(Article).count()
    return {'status':'ok','openai_configured':bool(OPENAI_KEY),'model':MODEL,'youtube_configured':bool(YOUTUBE_KEY),'article_count':count,'scheduler_running':scheduler.running,'timezone':preferences()['timezone'],'last_ingestion':json.loads(job.payload) if job else None,'jobs':[{'id':j.id,'next_run':str(j.next_run_time)} for j in scheduler.get_jobs()]}

@app.get('/api/cron/news')
async def cron_news(request:Request):
    from .serverless import check_cron,cleanup_limits
    check_cron(request,CRON_SECRET)
    result=await ingest()
    generate_briefing('morning');generate_briefing('evening')
    if datetime.now(ZoneInfo(preferences()['timezone'])).weekday()==6:generate_briefing('weekly')
    cleanup_limits()
    return result

@app.get('/api/cron/youtube')
async def cron_youtube(request:Request):
    from .serverless import check_cron,run_exclusive
    check_cron(request,CRON_SECRET)
    return await run_exclusive('youtube-refresh',scheduled_youtube)

# One-process production/local serving after the frontend build.
if (ROOT/'frontend'/'dist').is_dir():
    app.mount('/avatars',StaticFiles(directory=ROOT/'frontend'/'dist'/'avatars'),name='avatars')
    app.mount('/assets',StaticFiles(directory=ROOT/'frontend'/'dist'/'assets'),name='assets')
    if (ROOT/'frontend'/'dist'/'logos').is_dir():
        app.mount('/logos',StaticFiles(directory=ROOT/'frontend'/'dist'/'logos'),name='logos')
    @app.get('/')
    def index(): return FileResponse(ROOT/'frontend'/'dist'/'index.html')
    @app.get('/favicon.svg')
    def favicon(): return FileResponse(ROOT/'frontend'/'dist'/'favicon.svg',media_type='image/svg+xml')

app.add_middleware(SecurityEnvelope,origin_provider=lambda:PUBLIC_APP_URL,extra_origin_provider=lambda:DEPLOYMENT_ORIGIN)
from .cloud_proxy import CloudProxy
from .config import PROXY_SECRET
app.add_middleware(CloudProxy,origin_provider=lambda:PUBLIC_APP_URL,secret_provider=lambda:PROXY_SECRET if not SERVERLESS else '')
