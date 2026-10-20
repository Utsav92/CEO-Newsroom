"""Daily public uploads from a curated allowlist of official company channels.

Only public metadata is cached; videos play through YouTube's own player.
Reference: developers.google.com/youtube/v3/guides/implementation/videos
"""
import asyncio,json,re,html
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
import httpx
from sqlalchemy import select
from .database import Session,Video,YouTubeChannel,now_iso
from .config import YOUTUBE_KEY,TIMEZONE
from .personas import PERSONAS,BY_COMPANY
from .ai import AIUnavailable

REFRESH_TIME='07:30'
OFFICIAL_CHANNELS={p['company']:p['handle'] for p in PERSONAS}
locks={company:asyncio.Lock() for company in OFFICIAL_CHANNELS}
API_ROOT='https://www.googleapis.com/youtube/v3/'
MAX_VIDEOS=50
RETRY_DELAY=timedelta(minutes=15)
RETENTION=timedelta(days=30)

def instant(value):
    if not value:return None
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError,TypeError):return None

def utc_now():return datetime.now(timezone.utc)

def refresh_due(state,tz=TIMEZONE,now=None):
    now=now or utc_now()
    success=instant(state['last_success_at'])
    local_now=now.astimezone(ZoneInfo(tz));hour,minute=map(int,REFRESH_TIME.split(':'))
    scheduled=local_now.replace(hour=hour,minute=minute,second=0,microsecond=0)
    if success and state.get('status')=='available':
        local_success=success.astimezone(ZoneInfo(tz))
        if local_success.date()==local_now.date() and (local_now<scheduled or local_success>=scheduled):return False
    attempted=instant(state['last_attempt_at'])
    return not attempted or now-attempted>=RETRY_DELAY

def channel_state(company):
    handle=OFFICIAL_CHANNELS[company]
    with Session() as db:
        row=db.get(YouTubeChannel,company)
        return {'company':company,'handle':handle,'channel_url':'https://www.youtube.com/@'+handle,'channel_id':row.channel_id if row and row.handle.casefold()==handle.casefold() else None,'title':row.title if row else company,'last_attempt_at':row.last_attempt_at if row else None,'last_success_at':row.last_success_at if row else None,'status':row.status if row else 'not checked','detail':row.detail if row else ''}

def cached_videos(company=None,q=''):
    """Older/unverified cache entries never become official by sharing a title."""
    now=utc_now();words=q.casefold().split();result=[]
    with Session.begin() as db:
        states={s.company:s for s in db.scalars(select(YouTubeChannel)).all()}
        for row in db.scalars(select(Video)).all():
            v=json.loads(row.payload);c=v.get('company');state=states.get(c)
            fetched=instant(row.fetched_at)
            if not fetched or now-fetched>RETENTION:
                db.delete(row);continue
            if not state or c not in OFFICIAL_CHANNELS or state.handle.casefold()!=OFFICIAL_CHANNELS[c].casefold():continue
            if not v.get('official') or not state.channel_id or v.get('channel_id')!=state.channel_id or v.get('privacy_status')!='public':continue
            if company and c!=company:continue
            searchable=(v.get('title','')+' '+v.get('description','')+' '+c).casefold()
            if words and not all(word in searchable for word in words):continue
            result.append(v)
    return sorted(result,key=lambda v:v['published_at'],reverse=True)

async def api_get(client,method,key,**params):
    try:
        response=await client.get(API_ROOT+method,params={'key':key,**params})
    except httpx.HTTPError:
        raise AIUnavailable('YouTube could not be reached. Previously verified uploads remain available.') from None
    if response.status_code!=200:
        # Never echo provider messages, URLs or query parameters containing a key.
        reason=''
        try:reason=response.json().get('error',{}).get('errors',[{}])[0].get('reason','')
        except (ValueError,IndexError,AttributeError):pass
        detail='YouTube quota is exhausted; retry after quota resets.' if reason in ('quotaExceeded','dailyLimitExceeded') else 'Check that YouTube Data API v3 is enabled and the server key is valid.'
        raise AIUnavailable(f'YouTube API failed (HTTP {response.status_code}). {detail}')
    try:
        data=response.json()
        if not isinstance(data,dict) or not isinstance(data.get('items'),list):raise ValueError()
        return data
    except ValueError:raise AIUnavailable('YouTube returned an invalid response; this update was withheld.') from None

async def refresh_company(company,force=False,key=None,tz=TIMEZONE):
    if company not in OFFICIAL_CHANNELS:raise ValueError('Unknown company')
    key=YOUTUBE_KEY if key is None else key
    if not key:raise AIUnavailable('Add YOUTUBE_API_KEY to the server .env.local and enable YouTube Data API v3. Only official company uploads will be shown.')
    async with locks[company]:
        previous=channel_state(company)
        if not force and not refresh_due(previous,tz):return previous
        attempt=now_iso();handle=OFFICIAL_CHANNELS[company]
        with Session.begin() as db:
            row=db.get(YouTubeChannel,company)
            if not row:row=YouTubeChannel(company=company,handle=handle);db.add(row)
            row.last_attempt_at=attempt
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                channels=await api_get(client,'channels',key,part='id,snippet,contentDetails',forHandle='@'+handle)
                if len(channels['items'])!=1:raise AIUnavailable(f'The official @{handle} channel could not be resolved. No alternative channels were substituted.')
                channel=channels['items'][0];cid=channel.get('id','');snippet=channel.get('snippet',{})
                custom=snippet.get('customUrl','').lstrip('@').casefold()
                uploads=channel.get('contentDetails',{}).get('relatedPlaylists',{}).get('uploads','')
                if not re.fullmatch(r'UC[\w-]{22}',cid) or custom!=handle.casefold() or not uploads:
                    raise AIUnavailable('The official channel identity could not be validated. No uploads were added.')
                if previous['channel_id'] and previous['channel_id']!=cid:
                    raise AIUnavailable('The official handle now resolves to a different channel ID. This update was withheld for review.')
                listing=await api_get(client,'playlistItems',key,part='contentDetails',playlistId=uploads,maxResults=MAX_VIDEOS)
                ids=list(dict.fromkeys(item.get('contentDetails',{}).get('videoId','') for item in listing['items']))
                ids=[id for id in ids if re.fullmatch(r'[\w-]{11}',id)]
                details=await api_get(client,'videos',key,part='snippet,status',id=','.join(ids)) if ids else {'items':[]}
            videos=[];seen=set()
            for item in details['items']:
                s=item.get('snippet',{});status=item.get('status',{});id=item.get('id','')
                published=instant(s.get('publishedAt'))
                if id not in ids or id in seen or s.get('channelId')!=cid or status.get('privacyStatus')!='public' or status.get('uploadStatus')!='processed' or not published:continue
                seen.add(id)
                thumbs=s.get('thumbnails',{});thumb=next((thumbs[size].get('url','') for size in ['high','medium','default'] if size in thumbs),'')
                videos.append({'id':id,'title':html.unescape(s.get('title','')),'description':html.unescape(s.get('description',''))[:1200],'channel':snippet.get('title',company),'channel_id':cid,'channel_url':'https://www.youtube.com/channel/'+cid,'official_handle':handle,'official':True,'privacy_status':'public','published_at':published.isoformat(),'thumbnail':thumb if thumb.startswith('https://') else '', 'company':company,'presenter':BY_COMPANY[company]['id'],'url':'https://www.youtube.com/watch?v='+id,'embeddable':bool(status.get('embeddable',False))})
            with Session.begin() as db:
                # Replace this company's bounded upload snapshot atomically. Removed,
                # private, deleted and foreign-owner videos disappear after a refresh.
                for row in db.scalars(select(Video)).all():
                    if json.loads(row.payload).get('company')==company:db.delete(row)
                db.flush()
                for v in videos:db.add(Video(id=v['id'],payload=json.dumps(v),fetched_at=attempt))
                row=db.get(YouTubeChannel,company)
                row.handle=handle;row.channel_id=cid;row.title=snippet.get('title',company);row.uploads_playlist_id=uploads
                row.last_success_at=attempt;row.status='available';row.detail=f'{len(videos)} public official uploads checked'
            return channel_state(company)
        except AIUnavailable as exc:
            with Session.begin() as db:
                row=db.get(YouTubeChannel,company);row.status='unavailable';row.detail=str(exc)
            return channel_state(company)

async def refresh_all(force=False,key=None,tz=TIMEZONE):
    key=YOUTUBE_KEY if key is None else key
    if not key:return {'configured':False,'channels':[channel_state(c) for c in OFFICIAL_CHANNELS]}
    semaphore=asyncio.Semaphore(3)
    async def one(company):
        async with semaphore:return await refresh_company(company,force,key,tz)
    return {'configured':True,'channels':await asyncio.gather(*(one(c) for c in OFFICIAL_CHANNELS))}

async def youtube(company='OpenAI',q='',key=None,tz=TIMEZONE,force=False):
    key=YOUTUBE_KEY if key is None else key
    if not key:raise AIUnavailable('Add YOUTUBE_API_KEY to the server .env.local and enable YouTube Data API v3. Only official company uploads will be shown.')
    selected=None if company in ('all','') else company
    if selected and selected not in OFFICIAL_CHANNELS:raise ValueError('Unknown company')
    if selected:states=[await refresh_company(selected,force,key,tz)]
    else:states=(await refresh_all(force,key,tz))['channels']
    videos=cached_videos(selected,q[:120])
    warnings=[s['company']+': '+s['detail'] for s in states if s['status']=='unavailable']
    return {'videos':videos,'channels':states,'official':True,'cached':True,'updated_at':max((s['last_success_at'] for s in states if s['last_success_at']),default=None),'warnings':warnings,'daily_refresh_time':REFRESH_TIME,'timezone':tz}
