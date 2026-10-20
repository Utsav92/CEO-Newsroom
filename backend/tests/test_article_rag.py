import asyncio,json
import pytest
from fastapi.testclient import TestClient
from app import rag,services,main
from app.ai import AIUnavailable
from app.database import Article,ArticlePassage,ChatMessage

def test_sqlite_migration_keeps_reads_available_during_index_writes(tmp_path,monkeypatch):
    from sqlalchemy import create_engine,text
    from sqlalchemy.orm import sessionmaker
    from app import database
    engine=create_engine('sqlite:///'+str(tmp_path/'rag.db'))
    monkeypatch.setattr(database,'engine',engine);monkeypatch.setattr(database,'Session',sessionmaker(engine))
    monkeypatch.setattr(database,'DATABASE_URL','sqlite:///fixture')
    database.migrate();database.migrate()
    with engine.connect() as writer,engine.connect() as reader:
        assert reader.exec_driver_sql('PRAGMA journal_mode').scalar()=='wal'
        assert reader.execute(text('SELECT COUNT(*) FROM schema_versions')).scalar()==6
        writer.exec_driver_sql('BEGIN IMMEDIATE')
        writer.execute(text("UPDATE users SET name='Indexing fixture' WHERE id='local'"))
        assert reader.execute(text("SELECT name FROM users WHERE id='local'")).scalar()=='Your newsroom'
        writer.rollback()
    engine.dispose()

@pytest.fixture
def provider(monkeypatch):
    calls=[]
    async def embedding(texts):return [[1,0] for _ in texts]
    async def explain(instructions,context,schema,name):
        calls.append(context)
        passages=context['evidence']
        ids=[p['id'] for p in passages if p['selected_article']] or [p['id'] for p in passages[:1]]
        company=context['company_perspective']
        return {'answer':company+' fixture perspective.',**{k:{'text':company+' '+k+' fixture explanation.','basis':('inference' if k=='impact' else 'explanation') if ids else 'not_supported','passage_ids':ids} for k in ['meaning','mechanism','impact']}}
    monkeypatch.setattr(rag,'embed',embedding);monkeypatch.setattr(services,'embed',embedding)
    monkeypatch.setattr(rag,'structured',explain);monkeypatch.setattr(rag,'OPENAI_KEY','fixture-only')
    return calls

def test_index_only_publisher_text_and_reindex_changes(db,seed,provider):
    seed()
    with db.begin() as s:
        a=s.get(Article,'report-1');a.summary='INVENTED AI SUMMARY';a.excerpt='Publisher sentence one. '+('Long source text '*55)
    first=asyncio.run(rag.index_articles(['report-1']))
    assert first['embedded']>1
    with db() as s:
        rows=s.query(ArticlePassage).all()
        assert all('INVENTED' not in p.text for p in rows)
        assert all(len(p.text)<=420 for p in rows)
        old_ids={p.id for p in rows if p.kind=='excerpt'}
    assert asyncio.run(rag.index_articles(['report-1']))['embedded']==0
    with db.begin() as s:s.get(Article,'report-1').excerpt='Changed publisher excerpt.'
    asyncio.run(rag.index_articles(['report-1']))
    with db() as s:assert not old_ids & {p.id for p in s.query(ArticlePassage).all()}

def test_selected_article_stays_anchor_outside_date_filter(db,seed,provider):
    seed(published='2020-01-01',title='OpenAI training infrastructure')
    result=asyncio.run(services.chat('How does this work today?',article_id='report-1',period='today',topic='training',include_related=False))
    message=result['messages'][0]
    assert message['presenter']=='sam_altman'
    assert message['article_id']=='report-1'
    assert [s['title'] for s in message['explanation']['sections']]==['What it means','How it works','Likely impact']
    assert result['retrieval']['supporting_article_count']==0
    with db() as s:
        rows=s.query(ChatMessage).all()
        assert json.loads(rows[0].payload)['article_id']=='report-1'
        assert json.loads(rows[1].payload)['explanation']==message['explanation']

def test_each_company_gets_a_scoped_followup_in_shared_article_answers(db,seed,provider):
    seed(title='OpenAI and NVIDIA GPU partnership')
    with db.begin() as s:s.get(Article,'report-1').companies='["OpenAI","NVIDIA"]'
    result=asyncio.run(rag.explain_article('report-1','What are the next steps?',include_related=False))
    messages=result['messages']
    assert {m['presenter'] for m in messages}=={'sam_altman','jensen_huang'}
    assert len({m['follow_up_question'] for m in messages})==2
    assert all(len(m['reply_options'])>=2 and len(m['suggested_questions'])>=2 for m in messages)

def test_optional_related_reports_exclude_unrelated_company(db,seed,provider):
    seed(title='OpenAI training');seed('related',title='OpenAI training GPUs');seed('unrelated',company='Apple',title='Apple training')
    anchor,records,passages=asyncio.run(rag.retrieve_article_context('report-1','training',include_related=True))
    assert 'related' in records and 'unrelated' not in records
    assert any(not p['selected_article'] for p in passages)
    _,records,passages=asyncio.run(rag.retrieve_article_context('report-1','training',include_related=False))
    assert list(records)==['report-1'] and all(p['selected_article'] for p in passages)

@pytest.mark.parametrize('companies',[['OpenAI','NVIDIA'],['Anthropic','Google'],['OpenAI','NVIDIA','Google']])
def test_shared_article_each_company_gets_distinct_answer(db,seed,provider,companies):
    seed(title=' and '.join(companies)+' partnership')
    with db.begin() as s:s.get(Article,'report-1').companies=json.dumps(companies)
    result=asyncio.run(services.chat('What does this mean for each company?',article_id='report-1',include_related=False))
    assert [m['company_perspective'] for m in result['messages']]==companies
    assert len({m['text'] for m in result['messages']})==len(companies)
    assert all(m['citations'][0]['id']=='report-1' for m in result['messages'])
    assert {c['company_perspective'] for c in provider}==set(companies)

def test_question_adds_company_perspective_to_single_company_article(db,seed,provider):
    seed(company='NVIDIA',title='NVIDIA GPUs for model training')
    result=asyncio.run(services.chat('How would OpenAI benefit?',article_id='report-1',include_related=False))
    assert {m['company_perspective'] for m in result['messages']}=={'NVIDIA','OpenAI'}

def test_general_topic_and_followup_keep_all_presenters(db,seed,provider):
    seed(title='OpenAI model training');seed('gpu',company='NVIDIA',title='NVIDIA GPU training')
    first=asyncio.run(services.chat('How could NVIDIA GPUs benefit OpenAI?'))
    assert {m['company_perspective'] for m in first['messages']}=={'OpenAI','NVIDIA'}
    follow=asyncio.run(services.chat('What are their risks?',session_id=first['session_id']))
    assert {m['company_perspective'] for m in follow['messages']}=={'OpenAI','NVIDIA'}

@pytest.mark.parametrize('invalid',['unknown','missing','anchor'])
def test_withholds_invalid_passage_evidence(db,seed,provider,monkeypatch,invalid):
    seed();seed('related',title='OpenAI related training')
    async def bad(instructions,context,*args):
        ids=['made-up'] if invalid=='unknown' else [] if invalid=='missing' else [p['id'] for p in context['evidence'] if not p['selected_article']]
        return {'answer':'Fixture',**{k:{'text':'Fixture','basis':'reported','passage_ids':ids} for k in ['meaning','mechanism','impact']}}
    monkeypatch.setattr(rag,'structured',bad)
    with pytest.raises(AIUnavailable):asyncio.run(rag.explain_article('report-1','training'))

def test_no_reporting_keeps_each_company_and_reports_gap(db,provider):
    result=asyncio.run(services.chat('How do Google and Anthropic benefit?'))
    assert len(result['messages'])==2
    assert all(not m['citations'] and all(s['basis']=='not_supported' for s in m['explanation']['sections']) for m in result['messages'])

def test_missing_selected_article_returns_404(db):
    client=TestClient(main.app);token=client.get('/api/session').json()['token']
    response=client.post('/api/chat',headers={'X-Newsroom-Token':token},json={'question':'Explain this topic','article_id':'missing'})
    assert response.status_code==404

def test_grounding_review_is_repaired_and_revalidated_before_saving(db,seed,provider,monkeypatch):
    seed()
    original=rag.structured
    async def corrupt_review(instructions,context,schema,name):
        result=await original(instructions,context,schema,name)
        if name=='article_explanation_review':result['mechanism']['passage_ids']=['unverified-review-source']
        return result
    monkeypatch.setattr(rag,'structured',corrupt_review)
    result=asyncio.run(services.chat('How does this work?',article_id='report-1',include_related=False))
    assert len(provider)==3 and 'draft' in provider[1]
    assert all('unverified-review-source' not in [p['id'] for p in section['evidence']] for section in result['messages'][0]['explanation']['sections'])
    with db() as s:assert s.query(ChatMessage).count()==2

def test_known_prose_citation_markers_are_cosmetic_and_structured_sources_remain_valid():
    id='web:0123456789abcdef';passage=id+':research'
    records={id:{'id':id,'title':'Verified source','url':'https://example.org/source'}}
    passages=[{'id':passage,'article_id':id,'selected_article':False,'text':'Source text'}]
    result={'answer':'A qualified explanation ['+id+'].',**{key:{'text':'An explanation ('+passage+').','basis':'inference','passage_ids':[passage]} for key in ('meaning','mechanism','impact')}}
    message=rag.validate_explanation(result,'sam_altman','OpenAI',None,records,passages,None,'What does this mean?')
    assert 'web:' not in message['text']
    assert all('web:' not in s['text'] and s['evidence'][0]['id']==passage for s in message['explanation']['sections'])
    assert message['citations']==list(records.values())

def test_unknown_prose_citation_is_still_rejected():
    result={'answer':'An invented reference [web:deadbeefdeadbeef].',**{key:{'text':'A possible outcome.','basis':'inference','passage_ids':[]} for key in ('meaning','mechanism','impact')}}
    with pytest.raises(AIUnavailable,match='internal citation'):
        rag.validate_explanation(result,'sam_altman','OpenAI',None,{},[],None,'What could happen?')
