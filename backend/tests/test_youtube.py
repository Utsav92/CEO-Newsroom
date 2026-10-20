import asyncio,json
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import httpx,pytest
from fastapi.testclient import TestClient
from app import youtube,main
from app.database import Video,YouTubeChannel

COMPANIES=list(youtube.OFFICIAL_CHANNELS)
def cid(company):return 'UC'+str(COMPANIES.index(company)).zfill(22)
def video(company,id=None,owner=None,privacy='public',upload='processed',embeddable=True):
    return {'id':id or 'fixture'+str(COMPANIES.index(company)).zfill(4),'snippet':{'channelId':owner or cid(company),'title':company+' fixture upload','description':'Fixture GPU launch explanation','publishedAt':'2026-10-13T10:00:00Z','thumbnails':{'high':{'url':'https://example.org/fixture.jpg'}}},'status':{'privacyStatus':privacy,'uploadStatus':upload,'embeddable':embeddable}}

@pytest.fixture
def api_source(monkeypatch):
    source={'now':datetime(2026,10,13,20,tzinfo=timezone.utc),'videos':{c:[video(c)] for c in COMPANIES},'calls':[],'failures':set(),'handle_override':None,'channel_override':None,'extra':[]}
    handles={handle.casefold():c for c,handle in youtube.OFFICIAL_CHANNELS.items()}
    def response(request):
        method=request.url.path.rsplit('/',1)[-1];params=dict(request.url.params)
        source['calls'].append((method,{k:v for k,v in params.items() if k!='key'}))
        if method=='channels':
            company=handles[params['forHandle'].lstrip('@').casefold()]
            if company in source['failures']:return httpx.Response(403,json={'error':{'errors':[{'reason':'quotaExceeded'}],'message':'fixture-provider-secret-must-not-appear'}})
            return httpx.Response(200,json={'items':[{'id':source['channel_override'] or cid(company),'snippet':{'title':company,'customUrl':source['handle_override'] or '@'+youtube.OFFICIAL_CHANNELS[company]},'contentDetails':{'relatedPlaylists':{'uploads':'UU'+cid(company)[2:]}}}]})
        if method=='playlistItems':
            company=next(c for c in COMPANIES if 'UU'+cid(c)[2:]==params['playlistId'])
            return httpx.Response(200,json={'items':[{'contentDetails':{'videoId':v['id']}} for v in source['videos'][company]]})
        if method=='videos':
            ids=params['id'].split(',')
            return httpx.Response(200,json={'items':[v for rows in source['videos'].values() for v in rows if v['id'] in ids]+source['extra']})
        raise AssertionError('Unexpected YouTube API method: '+method)
    original=httpx.AsyncClient
    monkeypatch.setattr(youtube.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(response),**kwargs))
    monkeypatch.setattr(youtube,'YOUTUBE_KEY','fixture-key-not-a-credential')
    monkeypatch.setattr(youtube,'utc_now',lambda:source['now']);monkeypatch.setattr(youtube,'now_iso',lambda:source['now'].isoformat())
    return source

@pytest.mark.parametrize('company',COMPANIES)
def test_every_official_company_uses_own_uploads_and_checks_owner(db,api_source,company):
    result=asyncio.run(youtube.youtube(company))
    assert len(result['videos'])==1
    v=result['videos'][0]
    assert v['company']==company and v['channel_id']==cid(company) and v['official'] and v['privacy_status']=='public'
    assert [method for method,_ in api_source['calls']]==['channels','playlistItems','videos']
    assert api_source['calls'][0][1]['forHandle']=='@'+youtube.OFFICIAL_CHANNELS[company]
    assert api_source['calls'][1][1]['maxResults']=='50'

def test_filters_fan_reposts_private_unlisted_deleted_and_unlisted_ids(db,api_source):
    c='OpenAI';good=video(c);good['status']['embeddable']=False
    api_source['videos'][c]=[good,video(c,'fixture0101',owner=cid('Meta')),video(c,'fixture0102',privacy='private'),video(c,'fixture0103',privacy='unlisted'),video(c,'fixture0104',upload='deleted'),video(c,'fixture0105',upload='uploaded')]
    api_source['extra']=[video(c,'fixture0999')]
    result=asyncio.run(youtube.youtube(c))
    assert [v['id'] for v in result['videos']]==[good['id']]
    assert result['videos'][0]['embeddable'] is False
    with db() as s:assert s.query(Video).count()==1

def test_search_is_local_and_daily_cache_does_not_spend_more_quota(db,api_source):
    asyncio.run(youtube.youtube('NVIDIA'))
    assert len(api_source['calls'])==3
    assert len(asyncio.run(youtube.youtube('NVIDIA','GPU launch'))['videos'])==1
    assert asyncio.run(youtube.youtube('NVIDIA','unrelated topic'))['videos']==[]
    assert len(api_source['calls'])==3
    api_source['now']=datetime(2026,10,13,23,5,tzinfo=timezone.utc) # Next calendar day in London.
    asyncio.run(youtube.youtube('NVIDIA',tz='Europe/London'))
    assert len(api_source['calls'])==6

def test_all_channels_update_independently_on_partial_outage(db,api_source):
    api_source['failures'].add('Meta')
    result=asyncio.run(youtube.youtube('all'))
    assert len(result['videos'])==7
    assert len(result['channels'])==8 and len(result['warnings'])==1
    assert 'fixture-provider-secret' not in json.dumps(result)
    assert all(v['company']!='Meta' for v in result['videos'])

def test_missed_morning_schedule_catches_up_within_same_day(db,api_source):
    api_source['now']=datetime(2026,10,13,0,tzinfo=timezone.utc)
    asyncio.run(youtube.youtube('OpenAI'))
    api_source['now']=datetime(2026,10,13,9,tzinfo=timezone.utc)
    asyncio.run(youtube.youtube('OpenAI'))
    assert len(api_source['calls'])==6
    api_source['now']+=timedelta(minutes=5)
    asyncio.run(youtube.youtube('OpenAI'))
    assert len(api_source['calls'])==6

def test_failed_refresh_preserves_verified_uploads_and_backs_off(db,api_source):
    asyncio.run(youtube.youtube('Apple'))
    api_source['now']+=timedelta(days=1);api_source['failures'].add('Apple')
    result=asyncio.run(youtube.youtube('Apple'))
    assert result['videos'] and result['warnings']
    attempts=len(api_source['calls'])
    asyncio.run(youtube.youtube('Apple'))
    assert len(api_source['calls'])==attempts
    api_source['now']+=timedelta(minutes=16);api_source['failures'].clear()
    assert not asyncio.run(youtube.youtube('Apple'))['warnings']
    assert len(api_source['calls'])==attempts+3

def test_channel_identity_mismatch_withholds_update(db,api_source):
    api_source['handle_override']='@fan-channel'
    result=asyncio.run(youtube.youtube('Google'))
    assert not result['videos'] and result['warnings']
    assert len(api_source['calls'])==1
    with db() as s:assert s.query(Video).count()==0

def test_changed_channel_id_is_not_silently_accepted(db,api_source):
    asyncio.run(youtube.youtube('Google'))
    api_source['channel_override']=cid('Apple')
    result=asyncio.run(youtube.youtube('Google',force=True))
    assert result['videos'][0]['channel_id']==cid('Google')
    assert 'different channel ID' in result['warnings'][0]

def test_removed_video_disappears_after_refresh_and_old_cache_is_deleted(db,api_source):
    asyncio.run(youtube.youtube('Netflix'))
    api_source['videos']['Netflix']=[]
    assert asyncio.run(youtube.youtube('Netflix',force=True))['videos']==[]
    asyncio.run(youtube.youtube('NVIDIA'))
    api_source['now']+=timedelta(days=31)
    assert youtube.cached_videos()==[]
    with db() as s:assert s.query(Video).count()==0

def test_legacy_or_spoofed_cached_video_is_never_promoted_to_official(db,api_source):
    with db.begin() as s:s.add(Video(id='fixture9999',payload=json.dumps({'company':'OpenAI','title':'Official-looking fan video','channel_id':cid('OpenAI')})))
    assert youtube.cached_videos()==[]

@pytest.mark.parametrize('date',['2026-03-28T09:00:00+00:00','2026-10-24T09:00:00+00:00'])
def test_daily_refresh_keeps_local_0730_across_dst(db,date):
    main.schedule_youtube();job=main.scheduler.get_job('youtube-daily')
    next_time=job.trigger.get_next_fire_time(None,datetime.fromisoformat(date))
    assert next_time.astimezone(ZoneInfo('Europe/London')).strftime('%H:%M')=='07:30'

def test_manual_refresh_requires_session_and_status_never_exposes_key(db,api_source,monkeypatch):
    monkeypatch.setattr(main,'YOUTUBE_KEY','fixture-key-not-a-credential')
    client=TestClient(main.app)
    assert client.post('/api/youtube/refresh',json={'company':'OpenAI'}).status_code==403
    token=client.get('/api/session').json()['token'];headers={'X-Newsroom-Token':token}
    assert client.post('/api/youtube/refresh',headers=headers,json={'company':'FakeCorp'}).status_code==422
    result=client.post('/api/youtube/refresh',headers=headers,json={'company':'OpenAI'})
    assert result.status_code==200 and result.json()['videos'][0]['official']
    status=client.get('/api/youtube/status')
    assert status.status_code==200 and status.json()['configured']
    assert 'fixture-key' not in status.text
