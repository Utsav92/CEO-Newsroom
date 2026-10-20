import asyncio, json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from apscheduler.triggers.cron import CronTrigger
from PIL import Image
from app import ai, ingestion, services, main
from app.personas import PERSONAS
from app.database import Article, ChatMessage, Preference

@pytest.mark.parametrize('persona',PERSONAS,ids=[p['company'] for p in PERSONAS])
def test_each_company_routes_to_its_presenter(persona):
    companies,_=ai.classify(persona['company']+' releases a new product')
    assert persona['company'] in companies
    assert services.BY_COMPANY[persona['company']]['id']==persona['id']

def test_multicompany_and_neutral_routing():
    assert set(ai.entities('NVIDIA and Google announce a partnership'))=={'NVIDIA','Google'}
    assert ai.entities('Metadata in a pineapple database')==[]
    assert ai.classify('A new kitchen robot opens a restaurant')[0]==[]

def test_incidental_body_company_mention_does_not_route_a_story():
    title='Rivian spin-off hires former Ford executive'
    companies,_=ai.classify(title+' He formerly worked on Apple’s car project.',title=title)
    assert companies==[]

def test_semantic_routing_without_keyword():
    prototypes=[[1,0]]+[[0,1]]*7
    companies,_=ai.classify('The answer engine publisher introduces a new service',vector=[1,0],prototypes=prototypes)
    assert companies==['OpenAI']

def test_feed_normalization_dates_and_excerpt():
    source={'name':'Fixture publisher'}
    xml='''<rss version="2.0"><channel><title>Fixture</title><item><title>OpenAI news</title><link>https://example.org/report?utm_source=news&amp;keep=1</link><pubDate>Tue, 13 Oct 2026 10:00:00 GMT</pubDate><description>&lt;p&gt;Permitted &lt;b&gt;excerpt&lt;/b&gt;&lt;/p&gt;</description></item></channel></rss>'''
    row=ingestion.parse_feed(xml,source)[0]
    assert row['url']=='https://example.org/report?keep=1'
    assert row['excerpt']=='Permitted excerpt'
    assert row['published_at']=='2026-10-13T10:00:00+00:00'
    assert ingestion.iso_date('not a date') is None
    assert ingestion.canonical_url('javascript:alert(1)')==''

def test_missing_date_is_not_replaced_with_ingestion_time():
    row=ingestion.parse_feed('<rss><channel><item><title>Undated story</title><link>https://example.org/undated</link></item></channel></rss>',{'name':'Fixture'})[0]
    assert row['published_at'] is None

def test_updated_atom_timestamp_is_not_mislabeled_as_publication():
    xml='<feed xmlns="http://www.w3.org/2005/Atom"><title>Fixture</title><entry><title>An updated story</title><link href="https://example.org/updated"/><updated>2026-10-13T12:00:00Z</updated></entry></feed>'
    assert ingestion.parse_feed(xml,{'name':'Fixture'})[0]['published_at'] is None

def test_day_precision_is_preserved_and_can_be_filtered(db,seed):
    value=datetime.now(ZoneInfo(services.preferences()['timezone'])).date().isoformat()
    assert ingestion.iso_date(value)==value
    seed(published=value)
    assert len(services.articles(period='today'))==1

def test_deduplication_and_source_outage(db,monkeypatch):
    monkeypatch.setattr(ingestion,'OPENAI_KEY','')
    monkeypatch.setattr(ingestion,'REGISTRY',[{'id':'test','name':'Fixture','url':'https://example.org/feed','kind':'rss','company':'OpenAI'}])
    async def fetch(client,source):
        return [{'url':'https://example.org/real','title':'OpenAI fixture','published_at':None,'excerpt':'Fixture','image':None,'source':'Fixture'}]*2
    monkeypatch.setattr(ingestion,'fetch_source',fetch)
    first=asyncio.run(ingestion.ingest()); second=asyncio.run(ingestion.ingest())
    assert first['added']==1 and second['added']==0
    with db() as session: assert session.query(Article).count()==1
    async def unavailable(client,source): raise ValueError('Source unavailable')
    monkeypatch.setattr(ingestion,'fetch_source',unavailable)
    result=asyncio.run(ingestion.ingest())
    assert result['sources_available']==0 and result['added']==0

def test_category_pages_are_never_articles(monkeypatch):
    class Reply:
        status_code=200
        text='<a href="/hub/blog/category/research">Research</a><a href="/hub/blog/a-real-announcement">An announcement</a>'
        def raise_for_status(self): pass
    class Client:
        async def get(self,url): return Reply()
    async def allow(client,url): return True
    monkeypatch.setattr(ingestion,'allowed',allow)
    monkeypatch.setattr(ingestion,'html_metadata',lambda body,url,source:{'url':url,'title':'A real announcement'})
    rows=asyncio.run(ingestion.fetch_source(Client(),{'url':'https://www.perplexity.ai/hub/blog','name':'Fixture','kind':'html','prefix':'/hub/blog/'}))
    assert len(rows)==1 and '/category/' not in rows[0]['url']

def test_filters_saved_and_privacy_default(db,seed):
    seed(); seed('old-report','Apple',published=(datetime.now(timezone.utc)-timedelta(days=50)).isoformat())
    assert len(services.articles(company='OpenAI'))==1
    assert len(services.articles(period='today'))==1
    assert services.preferences()['personalization'] is False
    assert services.articles(saved=True)==[]
    with db.begin() as s: s.add(Preference(id='local',payload=json.dumps({'saved':['report-1']})))
    assert [a['id'] for a in services.articles(saved=True)]==['report-1']

def test_saved_article_remains_accessible_after_a_thousand_newer_reports(db,seed):
    seed('saved-old',published='2020-01-01T12:00:00+00:00')
    with db.begin() as s:
        s.add(Preference(id='local',payload=json.dumps({'saved':['saved-old']})))
        s.add_all([Article(id=f'new-{i}',url=f'https://example.org/new-{i}',title=f'New report {i}',source='Fixture publisher',published_at='2026-10-15T12:00:00+00:00',excerpt='Fixture reporting',summary='Fixture reporting',companies='["OpenAI"]',topics='["AI research"]',embedding='[1,0]') for i in range(1001)])
    saved=services.articles(saved=True)
    assert [a['id'] for a in saved]==['saved-old']
    assert saved[0]['url']=='https://example.org/saved-old'
    assert services.articles(saved=True,period='today')==[]

def test_briefing_includes_only_dated_available_reporting(db,seed):
    seed(); seed('old','Apple',published=(datetime.now(timezone.utc)-timedelta(days=8)).isoformat())
    briefing=services.generate_briefing()
    assert len(briefing['articles'])==1
    assert briefing['messages'][0]['presenter']=='sam_altman'
    assert briefing['messages'][0]['citations'][0]['id']=='report-1'

def test_empty_briefing_does_not_fabricate(db):
    b=services.generate_briefing()
    assert b['empty'] is True and b['articles']==[] and b['messages']==[]

@pytest.mark.parametrize('date',['2026-03-28T09:00:00+00:00','2026-10-24T09:00:00+00:00'])
def test_briefing_schedule_keeps_local_0800_across_dst(date):
    trigger=CronTrigger(hour=8,minute=0,timezone='Europe/London')
    next_time=trigger.get_next_fire_time(None,datetime.fromisoformat(date))
    assert next_time.astimezone(ZoneInfo('Europe/London')).hour==8

def test_chat_citations_and_history(db,seed,monkeypatch):
    seed()
    async def embedding(texts): return [[1,0]]
    async def answer(*args): return {'messages':[{'presenter':'sam_altman','text':'A supported fixture answer.','article_ids':['report-1']}]}
    monkeypatch.setattr(services,'embed',embedding); monkeypatch.setattr(services,'structured',answer)
    result=asyncio.run(services.chat('What did OpenAI publish?'))
    assert result['messages'][0]['citations'][0]['id']=='report-1'
    with db() as s: assert s.query(ChatMessage).count()==2

def test_chat_repairs_unverified_citation_before_saving(db,seed,monkeypatch):
    seed()
    calls=[]
    async def embedding(texts): return [[1,0]]
    async def answer(*args):
        calls.append(args)
        return {'messages':[{'presenter':'sam_altman','text':'Repaired answer' if len(calls)>1 else 'Unverified','answer_kind':'analysis','article_ids':['report-1'] if len(calls)>1 else ['invented']}]}
    monkeypatch.setattr(services,'embed',embedding); monkeypatch.setattr(services,'structured',answer)
    result=asyncio.run(services.chat('OpenAI news'))
    assert result['citation_repaired'] and len(calls)==2
    assert result['messages'][0]['text']=='Repaired answer'
    assert result['messages'][0]['citations'][0]['id']=='report-1'
    with db() as s:assert all('Unverified' not in row.payload for row in s.query(ChatMessage).all())

def test_unrelated_presenter_is_corrected(db,seed,monkeypatch):
    seed()
    async def embedding(texts): return [[1,0]]
    async def answer(*args): return {'messages':[{'presenter':'tim_cook','text':'Fixture answer','article_ids':['report-1']}]}
    monkeypatch.setattr(services,'embed',embedding); monkeypatch.setattr(services,'structured',answer)
    result=asyncio.run(services.chat('OpenAI news'))
    assert result['messages'][0]['presenter']=='sam_altman'

def test_selected_ceo_explains_missing_reporting(db,monkeypatch):
    async def answer(*args):return {'messages':[{'presenter':'jensen_huang','text':'Without current reporting I can explain the general factors to watch, but cannot confirm a new event.','answer_kind':'general_explanation','article_ids':[]}]}
    monkeypatch.setattr(services,'structured',answer)
    result=asyncio.run(services.chat('What is the latest?',presenter='jensen_huang'))
    assert result['messages'][0]['presenter']=='jensen_huang'
    assert result['messages'][0]['citations']==[]

def test_company_ceo_delivers_a_grounded_narrator_answer(db,seed,monkeypatch):
    seed(company='NVIDIA',title='NVIDIA publishes research')
    async def embedding(texts): return [[1,0]]
    async def answer(*args): return {'messages':[{'presenter':'newsroom','text':'A supported source-backed answer.','article_ids':['report-1']}]}
    monkeypatch.setattr(services,'embed',embedding);monkeypatch.setattr(services,'structured',answer)
    result=asyncio.run(services.chat('What did NVIDIA announce?'))
    assert result['messages'][0]['presenter']=='jensen_huang'
    assert result['messages'][0]['citations'][0]['id']=='report-1'

def test_missing_evidence_uses_reasoning_without_an_embedding_call(db,monkeypatch):
    async def never(*args): raise AssertionError('Should not call AI')
    async def answer(*args):return {'messages':[{'presenter':'jensen_huang','text':'I cannot confirm what happened today; generally, product launches and demand could affect the company.','answer_kind':'general_explanation','article_ids':[]}]}
    monkeypatch.setattr(services,'embed',never)
    monkeypatch.setattr(services,'structured',answer)
    result=asyncio.run(services.chat('What happened at NVIDIA today?'))
    assert result['retrieval_count']==0
    assert result['messages'][0]['citations']==[]

def test_missing_api_keys_are_clear(monkeypatch):
    monkeypatch.setattr(ai,'OPENAI_KEY','')
    with pytest.raises(ai.AIUnavailable,match='not configured'): asyncio.run(ai.embed(['test']))
    monkeypatch.setattr(services,'YOUTUBE_KEY','')
    with pytest.raises(ai.AIUnavailable,match='YOUTUBE_API_KEY'): asyncio.run(services.youtube())

def test_admin_auth_origin_and_remote_host(db,monkeypatch):
    async def answer(*args):return {'messages':[{'presenter':'newsroom','text':'A general explanation with no current event claim.','answer_kind':'general_explanation','article_ids':[]}]}
    monkeypatch.setattr(services,'structured',answer)
    client=TestClient(main.app)
    assert client.post('/api/news/refresh',json={}).status_code==403
    token=client.get('/api/session').json()['token']
    assert client.post('/api/chat',json={'question':'No reporting'},headers={'X-Newsroom-Token':token,'Origin':'https://attacker.example'}).status_code==403
    assert client.get('/api/health',headers={'Host':'attacker.example'}).status_code==403
    response=client.post('/api/chat',json={'question':'No reporting'},headers={'X-Newsroom-Token':token})
    assert response.status_code==200

def test_invalid_company_period_and_timezone(db):
    client=TestClient(main.app); token=client.get('/api/session').json()['token']; headers={'X-Newsroom-Token':token}
    assert client.get('/api/news/company/FakeCorp').status_code==404
    assert client.get('/api/news?period=century').status_code==422
    assert client.post('/api/chat',json={'question':'Test','period':'century'},headers=headers).status_code==422
    assert client.put('/api/preferences',json={'timezone':'Made/Up'},headers=headers).status_code==422

def test_all_avatar_variants_are_valid_images():
    root=Path(__file__).resolve().parents[2]/'assets'/'avatars'
    for p in PERSONAS:
        for suffix,size in [('.png',(512,768)),('_profile.png',(256,256)),('_thumb.webp',(96,96))]:
            im=Image.open(root/(p['id']+suffix))
            assert im.size==size and im.mode=='RGBA'
            assert im.getchannel('A').getextrema()==(0,255)

def test_checkerboard_background_was_removed():
    root=Path(__file__).resolve().parents[2]/'assets'/'avatars'
    im=Image.open(root/'sam_altman.png')
    # This location is inside the source crop, not the transparent letterbox.
    assert im.getpixel((100,0))[3]==0
