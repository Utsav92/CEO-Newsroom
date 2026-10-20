import asyncio,json
import httpx,pytest
from fastapi.testclient import TestClient
from app import video_understanding as reader, video_rag, youtube, rag, services, main
from app.ai import AIUnavailable
from app.database import YouTubeChannel,ChatMessage

VIDEO={'id':'fixture0000','title':'OpenAI and NVIDIA demo','description':'Official metadata only','company':'OpenAI','presenter':'sam_altman','channel':'OpenAI','official':True,'url':'https://www.youtube.com/watch?v=fixture0000','published_at':'2026-10-13T10:00:00Z','thumbnail':'','duration_seconds':120}
ANALYSIS={'summary':'An interface demonstration','limitations':'A demo does not establish general performance.','observations':[{'timestamp':'00:25','modality':'audio_visual','observation':'The speaker describes a task while a visual interface shows its result.','uncertainty':'No comparative benchmark is shown.'}]}

@pytest.fixture
def video_provider(monkeypatch):
    fixture={'body':ANALYSIS,'status':200,'calls':[],'finish':'completed'}
    def respond(request):
        fixture['calls'].append(json.loads(request.content))
        if fixture['status']!=200:return httpx.Response(fixture['status'],json={'error':{'message':'fixture-secret-never-expose'}})
        return httpx.Response(200,json={'status':fixture['finish'],'steps':[{'type':'thought','summary':[{'type':'text','text':'Ignored private reasoning'}]},{'type':'model_output','content':[{'type':'text','text':json.dumps(fixture['body'])}]}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(reader.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    monkeypatch.setattr(reader,'GEMINI_KEY','fixture-video-key');reader._cache.clear();reader._locks.clear()
    return fixture

def test_actual_youtube_url_audio_visual_evidence_and_question_cache(video_provider):
    async def run():
        first=await reader.understand_video(VIDEO,'Explain the demo at 00:25')
        second=await reader.understand_video(VIDEO,'Explain the demo at 00:25')
        third=await reader.understand_video(VIDEO,'What is the chart showing?')
        return first,second,third
    first,second,third=asyncio.run(run())
    assert first['observations'][0]['modality']=='audio_visual' and second['cached'] and not third['cached']
    assert len(video_provider['calls'])==2
    assert video_provider['calls'][0]['input'][0]=={'type':'video','uri':VIDEO['url']}
    assert 'audio AND visual' in video_provider['calls'][0]['input'][1]['text']
    assert video_provider['calls'][0]['store'] is False

def test_concurrent_identical_questions_coalesce(video_provider):
    async def run():return await asyncio.gather(*(reader.understand_video(VIDEO,'Same question') for _ in range(4)))
    result=asyncio.run(run());assert len(video_provider['calls'])==1 and sum(m['cached'] for m in result)==3
    assert not reader._locks

def test_video_quick_reply_retains_the_ceos_clarifying_question(video_provider):
    history=[{'presenter':'sam_altman','video_id':VIDEO['id'],'text':'A video explanation.','follow_up_question':'Are you learning the basics or evaluating a technical implementation?'}]
    asyncio.run(reader.understand_video(VIDEO,'Learning the basics',history=history))
    prompt=video_provider['calls'][0]['input'][1]['text']
    assert history[0]['follow_up_question'] in prompt and 'Learning the basics' in prompt

@pytest.mark.parametrize('status',[400,401,403,404,429,500])
def test_provider_failure_never_falls_back_or_exposes_response(video_provider,status):
    video_provider['status']=status
    with pytest.raises(AIUnavailable) as exc:asyncio.run(reader.understand_video(VIDEO,'Explain'))
    assert 'fixture-secret' not in str(exc.value) and not reader._cache

@pytest.mark.parametrize('bad',[{**ANALYSIS,'observations':[]},{**ANALYSIS,'observations':[{**ANALYSIS['observations'][0],'timestamp':'02:01'}]},{**ANALYSIS,'observations':[{**ANALYSIS['observations'][0],'modality':'metadata'}]},{**ANALYSIS,'observations':[{**ANALYSIS['observations'][0],'timestamp':'00:99'}]}])
def test_invalid_evidence_or_out_of_range_timestamp_is_withheld(video_provider,bad):
    video_provider['body']=bad
    with pytest.raises(AIUnavailable):asyncio.run(reader.understand_video(VIDEO,'Explain'))
    assert not reader._cache

def test_truncated_provider_output_is_withheld(video_provider):
    video_provider['finish']='incomplete'
    with pytest.raises(AIUnavailable):asyncio.run(reader.understand_video(VIDEO,'Explain'))

def test_missing_video_key_does_not_call_provider(video_provider,monkeypatch):
    monkeypatch.setattr(reader,'GEMINI_KEY','')
    with pytest.raises(AIUnavailable,match='not connected'):asyncio.run(reader.understand_video(VIDEO,'Explain'))
    assert not video_provider['calls']

def test_unverified_or_overlong_video_does_not_call_provider(video_provider):
    for video in [{**VIDEO,'official':False},{**VIDEO,'duration_seconds':10801}]:
        with pytest.raises(AIUnavailable):asyncio.run(reader.understand_video(video,'Explain'))
    assert not video_provider['calls']

@pytest.fixture
def explain_provider(monkeypatch):
    calls=[]
    async def verified(id):return dict(VIDEO)
    async def analysis(*args):return {**ANALYSIS,'observations':[{**ANALYSIS['observations'][0],'seconds':25}],'model':'fixture-model','cached':False}
    async def embed(texts):return [[1,0] for _ in texts]
    async def structured(instructions,context,schema,name):
        calls.append(context)
        ids=[p['id'] for p in context['evidence'] if p.get('source_kind')=='video_analysis']
        return {'answer':context['company_perspective']+' video interpretation.',**{k:{'text':'A fixture explanation grounded in the observation.','basis':'inference' if k=='impact' else 'explanation','passage_ids':ids} for k in ['meaning','mechanism','impact']}}
    monkeypatch.setattr(video_rag,'verified_video',verified);monkeypatch.setattr(video_rag,'understand_video',analysis)
    monkeypatch.setattr(video_rag,'embed',embed);monkeypatch.setattr(rag,'structured',structured)
    return calls

def test_video_qa_routes_each_company_and_saves_scope_and_timestamp(db,explain_provider):
    result=asyncio.run(services.chat('How does this benefit OpenAI and NVIDIA?',video_id=VIDEO['id'],include_related=False))
    assert {m['company_perspective'] for m in result['messages']}=={'OpenAI','NVIDIA'}
    assert result['retrieval']['video_understood']
    for m in result['messages']:
        assert m['video_id']==VIDEO['id'] and m['article_id'] is None
        evidence=m['explanation']['sections'][0]['evidence'][0]
        assert evidence['source_kind']=='video_analysis' and evidence['url'].endswith('&t=25s')
        assert 'AI understanding' in m['explanation']['evidence_note']
    with db() as s:assert json.loads(s.query(ChatMessage).first().payload)['video_id']==VIDEO['id']
    followup=asyncio.run(services.chat('Why does that matter?',video_id=VIDEO['id'],session_id=result['session_id'],include_related=False))
    assert len(followup['messages'])==2

def test_selected_video_requires_actual_observation_citations(db,explain_provider,monkeypatch):
    async def metadata_only(*args):
        return {'explanation':{'sections':[{'basis':'explanation','evidence':[{'source_kind':'video_metadata'}]}]}}
    monkeypatch.setattr(video_rag,'explain_perspective',metadata_only)
    with pytest.raises(AIUnavailable,match='did not cite'):asyncio.run(video_rag.explain_video(VIDEO['id'],'Explain',include_related=False))
    with db() as s:assert s.query(ChatMessage).count()==0

@pytest.mark.parametrize('foreign',[True,False])
def test_video_owner_and_public_status_are_reverified(db,monkeypatch,foreign):
    with db.begin() as s:s.add(YouTubeChannel(company='OpenAI',handle=youtube.OFFICIAL_CHANNELS['OpenAI'],channel_id='UC'+'0'*22,title='OpenAI'))
    async def metadata(*args,**kwargs):
        return {'items':[{'id':VIDEO['id'],'snippet':{'channelId':'UC'+'1'*22 if foreign else 'UC'+'0'*22,'publishedAt':VIDEO['published_at']},'status':{'privacyStatus':'public' if foreign else 'private','uploadStatus':'processed'}}]}
    monkeypatch.setattr(video_rag,'api_get',metadata);monkeypatch.setattr(video_rag,'YOUTUBE_KEY','fixture-only')
    with pytest.raises(video_rag.VideoNotFound):asyncio.run(video_rag.verified_video(VIDEO['id']))

def test_api_rejects_invalid_or_ambiguous_scope(db):
    with TestClient(main.app) as client:
        token=client.get('/api/session').json()['token'];headers={'X-Newsroom-Token':token}
        for body in [{'question':'Explain','video_id':'bad url'},{'question':'Explain','video_id':VIDEO['id'],'article_id':'article'}]:
            assert client.post('/api/chat',json=body,headers=headers).status_code==422

def test_api_video_understanding_routes_chat(db,explain_provider):
    with TestClient(main.app) as client:
        token=client.get('/api/session').json()['token']
        response=client.post('/api/chat',json={'question':'Explain the video','video_id':VIDEO['id'],'include_related':False},headers={'X-Newsroom-Token':token})
        assert response.status_code==200 and response.json()['retrieval']['scope']=='video'
