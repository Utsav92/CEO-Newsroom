import asyncio,json
import pytest
from app import services,rag,answers
from app.database import Article,ChatMessage
from app.ai import AIUnavailable

def test_followup_keeps_prior_article_outside_fresh_filter_and_drops_history_ids(db,seed,monkeypatch):
    seed('old-story',title='OpenAI faces a legal complaint',published='2020-01-01T12:00:00+00:00',embedding=[0,1])
    seed('new-story',title='OpenAI releases a different product',embedding=[1,0])
    old=services.articles(q='legal complaint')[0]
    session=services.save_chat_result('Explain the complaint.',None,{'messages':[{'presenter':'sam_altman','text':'The report describes a complaint.','citations':[old,{'id':'invented-history-id'}]}]})['session_id']
    calls=[]
    async def embedding(texts):return [[1,0]]
    async def generate(instructions,context,schema,name):
        calls.append(context)
        assert context['evidence'][0]['id']=='old-story'
        assert 'invented-history-id' not in json.dumps(context)
        assert schema['properties']['messages']['items']['properties']['article_ids']['items']['enum'][0]=='old-story'
        return {'messages':[{'presenter':'sam_altman','text':'Yes, it could create costs and uncertainty; the outcome depends on how the complaint proceeds.','answer_kind':'analysis','article_ids':['old-story']}]}
    monkeypatch.setattr(services,'embed',embedding);monkeypatch.setattr(services,'structured',generate)
    result=asyncio.run(services.chat('is this a problem?',session_id=session,period='today'))
    message=result['messages'][0]
    assert message['presenter']=='sam_altman' and message['answer_kind']=='analysis'
    assert message['citations'][0]['id']=='old-story' and message['assessment_note']
    assert len(calls)==1

def test_repeated_bad_citations_generate_fresh_conditional_assessment(db,seed,monkeypatch):
    seed();calls=[]
    async def embedding(texts):return [[1,0]]
    async def generate(instructions,context,schema,name):
        calls.append(name)
        if name!='news_answer_assessment':return {'messages':[{'presenter':'sam_altman','text':'Unsupported draft must never appear','answer_kind':'source_based','article_ids':['made-up']}]}
        assert context['evidence']==[]
        assert 'article_ids' not in schema['properties']['messages']['items']['properties']
        return {'messages':[{'presenter':'sam_altman','text':'If the concern leads to restrictions, it could increase costs. That is a possible scenario, not an established outcome.','answer_kind':'prediction'}]}
    monkeypatch.setattr(services,'embed',embedding);monkeypatch.setattr(services,'structured',generate)
    result=asyncio.run(services.chat('Could this affect OpenAI?'))
    message=result['messages'][0]
    assert message['answer_kind']=='prediction' and message['citations']==[] and result['citation_repaired']
    assert calls==['news_answer','news_answer_repair','news_answer_assessment']
    assert 'could not be verified' in message['assessment_note']
    with db() as s:assert all('Unsupported draft' not in r.payload for r in s.query(ChatMessage).all())

def test_general_prediction_does_not_invent_current_reporting(db,monkeypatch):
    async def generate(instructions,context,schema,name):
        assert context['evidence']==[] and schema['properties']['messages']['items']['properties']['article_ids']['maxItems']==0
        assert 'Allegations are claims' in instructions
        return {'messages':[{'presenter':'newsroom','text':'If adoption grows, demand could rise; that depends on pricing and capability.','answer_kind':'prediction','article_ids':[]}]}
    monkeypatch.setattr(services,'structured',generate)
    result=asyncio.run(services.chat('What might happen if adoption grows?'))
    assert result['retrieval_count']==0
    assert result['messages'][0]['answer_kind']=='prediction' and 'not a confirmed fact' in result['messages'][0]['assessment_note']

def test_conditional_article_assessment_can_be_uncited_but_reported_fact_cannot():
    data={'answer':'If restrictions result, this could increase costs.',**{k:{'text':'If restrictions result, costs could increase.','basis':'inference','passage_ids':[]} for k in ['meaning','mechanism','impact']}}
    message=rag.validate_explanation(data,'sam_altman','OpenAI',None,{},[],None,'Is this a problem?')
    assert all(s['basis']=='inference' and not s['citations'] for s in message['explanation']['sections'])
    data['meaning']['basis']='reported'
    with pytest.raises(AIUnavailable,match='lacked citations'):rag.validate_explanation(data,'sam_altman','OpenAI',None,{},[],None,'Is this a problem?')

def test_citation_free_fallback_still_rejects_a_fabricated_source():
    data={'messages':[{'presenter':'sam_altman','text':'An unverified claim','answer_kind':'analysis','article_ids':['invented']}]}
    with pytest.raises(ValueError):answers.validate_answer(data,[],['OpenAI'],uncited=True)

def test_company_spokesperson_language_is_regenerated(db,seed,monkeypatch):
    seed();calls=[]
    async def embedding(texts):return [[1,0]]
    async def generate(*args):
        calls.append(args)
        return {'messages':[{'presenter':'sam_altman','text':'We are engaging regulators on behalf of our company.' if len(calls)==1 else 'OpenAI could face extra scrutiny; the report does not establish the outcome.','answer_kind':'analysis','article_ids':['report-1']}]}
    monkeypatch.setattr(services,'embed',embedding);monkeypatch.setattr(services,'structured',generate)
    result=asyncio.run(services.chat('Is this a problem for OpenAI?'))
    assert len(calls)==2 and result['citation_repaired']
    assert result['messages'][0]['text'].startswith('OpenAI could')
