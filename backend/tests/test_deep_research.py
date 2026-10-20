import asyncio,copy,json,httpx
import pytest
from app import ai,answers,research,services,rag
from app.database import ChatMessage

def web_result():
    first='An original technical source describes a retrieval stage followed by generation, and notes evaluation limits. [Original](https://platform.openai.com/docs/guides/retrieval)'
    second='An independent technical evaluation describes failure modes and stresses checking retrieved evidence. [Evaluation](https://arxiv.org/abs/2005.11401)'
    text=first+'\n\n'+second
    return {'status':'completed','output':[{'type':'web_search_call','status':'completed','action':{'sources':[{'url':'https://platform.openai.com/docs/guides/retrieval'},{'url':'https://arxiv.org/abs/2005.11401'}]}},{'type':'message','content':[{'type':'output_text','text':text,'annotations':[{'type':'url_citation','url':url,'title':title,'start_index':text.index(label),'end_index':text.index(label)+len(label)} for url,title,label in [('https://platform.openai.com/docs/guides/retrieval','Original research','[Original]'),('https://arxiv.org/abs/2005.11401','Independent evaluation','[Evaluation]')]]}]}]}

def test_research_accepts_only_tool_citations_and_preserves_provenance():
    rows=research.extract_sources(web_result(),['OpenAI'])
    assert len(rows)==2 and all(r['source_kind']=='web_research' for r in rows)
    assert rows[0]['published_at'] is None and rows[0]['companies']==['OpenAI']
    assert 'retrieval stage' in rows[0]['excerpt'] and 'failure modes' not in rows[0]['excerpt']
    assert 'independent technical evaluation' in rows[1]['excerpt']
    forged=web_result();forged['output'][1]['content'][0]['annotations'][0]['url']='https://invented.example/fake'
    assert len(research.extract_sources(forged,[]))==1
    unsearched=web_result();unsearched['output']=unsearched['output'][1:]
    assert research.extract_sources(unsearched,[])==[]
    incomplete=web_result();incomplete['status']='incomplete'
    assert research.extract_sources(incomplete,[])==[]

@pytest.mark.parametrize('url',['http://127.0.0.1/private','http://localhost/a','http://router.local/a','file:///secret','https://user:password@example.com/a','http://[::1]/a'])
def test_research_rejects_nonpublic_or_secret_bearing_links(url):
    assert research.public_url(url) is None

def test_source_registry_accepts_real_subdomains_and_rejects_lookalikes_and_seo_sites():
    assert research.trusted_source('https://platform.openai.com/docs/guides/retrieval')
    assert research.trusted_source('https://arxiv.org/abs/2005.11401')
    assert not research.trusted_source('https://openai.com.untrusted.example/comparison')
    assert not research.trusted_source('https://random-seo.example/rag-guide')
    assert not research.trusted_source('https://community.openai.com/t/forum-post')

def test_live_research_is_required_bounded_cached_and_copied(monkeypatch):
    research._cache.clear();calls=[]
    async def api(path,body):
        calls.append(body)
        assert path=='responses' and body['tools'][0]['type']=='web_search'
        assert body['tool_choice']=='required' and body['store'] is False
        assert 'filters' not in body['tools'][0]  # The configured 4.1 model does not support provider filters.
        assert 'search_query' in json.loads(body['input'])
        assert body['include']==['web_search_call.action.sources']
        return web_result()
    monkeypatch.setattr(ai,'OPENAI_KEY','fixture-only');monkeypatch.setattr(ai,'api',api)
    async def plan(context):return {'primary':'retrieval documentation','independent':'retrieval limitations research'}
    monkeypatch.setattr(research,'plan_searches',plan)
    async def read_sources(*args):return []
    monkeypatch.setattr(research,'read_search_sources',read_sources)
    async def run():
        first=await research.research_sources('How does retrieval work?',[],['OpenAI'])
        second=await research.research_sources('How does retrieval work?',[],['OpenAI'])
        second[0][0]['excerpt']='Changed only in this copy'
        third=await research.research_sources('How does retrieval work?',[],['OpenAI'])
        return first,second,third
    first,second,third=asyncio.run(run())
    assert len(calls)==2 and first[1]['web_source_count']==2 and first[1]['status']=='web_and_sources'
    assert not first[1]['cached'] and second[1]['cached'] and third[0][0]['excerpt']==first[0][0]['excerpt']
    research._cache.clear()

def test_research_outage_and_selected_source_only_are_honest(monkeypatch):
    async def failed(*args):raise ai.AIUnavailable('fixture-secret-provider-error')
    monkeypatch.setattr(ai,'OPENAI_KEY','fixture-only');monkeypatch.setattr(ai,'api',failed)
    rows,meta=asyncio.run(research.research_sources('An uncached question',[],[]))
    assert rows==[] and meta['status']=='sources_only' and 'unavailable' in meta['note']
    assert 'secret' not in json.dumps(meta)
    rows,meta=asyncio.run(research.research_sources('Explain only this source',[],[],enabled=False))
    assert rows==[] and 'turned off' in meta['note']

def sections(id='report-1'):
    return [{'title':title,'text':'A developed explanation with assumptions, practical constraints and a qualified assessment.','basis':'explanation' if i<2 else 'inference','article_ids':[id]} for i,title in enumerate(answers.RESEARCH_TITLES)]

def test_deep_sections_are_cited_saved_and_rejected_if_they_invent_sources(db,seed,monkeypatch):
    seed()
    async def embedding(texts):return [[1,0]]
    calls=[]
    async def generated(instructions,context,schema,name):
        calls.append(name)
        assert '450-700 words' in instructions and 'research_sections' in schema['properties']['messages']['items']['required']
        body=sections()
        if len(calls)==1:body[0]['article_ids']=['invented-nested-citation']
        return {'messages':[{'presenter':'sam_altman','text':'A direct, qualified answer.','answer_kind':'analysis','article_ids':['report-1'],'research_sections':body}]}
    monkeypatch.setattr(services,'embed',embedding);monkeypatch.setattr(services,'structured',generated)
    result=asyncio.run(services.chat('How does this affect OpenAI?'))
    message=result['messages'][0]
    assert result['citation_repaired'] and len(calls)==2
    assert len(message['explanation']['sections'])==5 and all(s['citations'][0]['id']=='report-1' for s in message['explanation']['sections'])
    assert message['research']['status']=='sources_only'
    with db() as s:
        stored=json.loads(s.query(ChatMessage).filter_by(role='assistant').one().payload)
        assert stored['explanation']==message['explanation']
        assert 'invented-nested-citation' not in json.dumps(stored)

def test_source_claims_in_deep_sections_require_citations(db,seed):
    seed();row={'presenter':'sam_altman','text':'A direct answer.','answer_kind':'analysis','article_ids':['report-1'],'research_sections':sections()}
    row['research_sections'][0]['article_ids']=[]
    with pytest.raises(ValueError,match='need citations'):answers.validate_answer({'messages':[row]},services.articles(),['OpenAI'])

def test_internal_citation_metadata_never_leaks_into_answer_text(db,seed):
    seed();row={'presenter':'sam_altman','text':'An answer (article_ids: [report-1]).','answer_kind':'analysis','article_ids':['report-1'],'research_sections':sections()}
    with pytest.raises(ValueError,match='internal citation IDs'):answers.validate_answer({'messages':[row]},services.articles(),['OpenAI'])

def test_forecasts_are_not_labeled_as_established_reporting(db,seed):
    seed();body=sections();body[-1]['basis']='reported'
    row={'presenter':'sam_altman','text':'A qualified direct answer.','answer_kind':'analysis','article_ids':['report-1'],'research_sections':body}
    with pytest.raises(ValueError,match='assessment'):answers.validate_answer({'messages':[row]},services.articles(),['OpenAI'])

def test_article_research_keeps_anchor_and_review_depth(db,seed,monkeypatch):
    seed();calls=[]
    async def embedding(texts):return [[1,0] for _ in texts]
    async def live(*args,**kwargs):return research.extract_sources(web_result(),['OpenAI']),{'status':'web_and_sources','web_source_count':2,'checked_at':'2026-10-15','note':'Fixture research','cached':False}
    async def generate(instructions,context,schema,name):
        calls.append((instructions,context,name))
        assert '450-700 words' in instructions
        assert 'three concise' not in instructions and '45-100 words' not in instructions
        assert any(p.get('source_kind')=='web_research' for p in context['evidence'])
        ids=[p['id'] for p in context['evidence']]
        return {'answer':'A developed direct answer.',**{key:{'text':'A detailed explanation grounded in the provided evidence.','basis':'inference' if key=='impact' else 'explanation','passage_ids':ids} for key in ['meaning','mechanism','impact']}}
    monkeypatch.setattr(rag,'embed',embedding);monkeypatch.setattr(rag,'structured',generate);monkeypatch.setattr(rag,'research_sources',live)
    result=asyncio.run(rag.explain_article('report-1','How does this work?',include_related=True))
    assert len(calls)==2 and 'must not compress' in calls[1][0]
    message=result['messages'][0]
    assert message['article_id']=='report-1' and message['research']['source_count']==3
    assert any(a.get('source_kind')=='web_research' for a in message['citations'])

def test_generation_budget_grows_for_answers_without_enlarging_feed_summaries(monkeypatch):
    calls=[]
    async def api(path,body):
        calls.append(body)
        return {'status':'completed','output':[{'content':[{'type':'output_text','text':'{}'}]}]}
    monkeypatch.setattr(ai,'api',api)
    for name in ['news_summary','news_answer','article_topic_explanation','article_explanation_review']:
        asyncio.run(ai.structured('Instructions',{},ai.object_schema({}),name))
    assert [c['max_output_tokens'] for c in calls]==[2600,9000,6500,6500]

def test_live_researched_answers_are_reviewed_for_quality_before_being_returned(db,seed):
    seed();calls=[]
    async def generate(instructions,context,schema,name):
        calls.append(name)
        body=sections()
        if name=='news_answer_review':
            assert 'draft' in context and 'unsupported absolutes' in instructions
            body[1]['text']='A reviewed implementation plan with evaluation and qualified cost assumptions.'
        return {'messages':[{'presenter':'sam_altman','text':'A direct answer.','answer_kind':'analysis','article_ids':['report-1'],'research_sections':body}]}
    result=asyncio.run(answers.answer_question('How should this be implemented?',services.articles(),['OpenAI'],context={'research':{'status':'web_and_sources'}},generator=generate))
    assert calls==['news_answer','news_answer_review']
    assert result['messages'][0]['explanation']['sections'][1]['text'].startswith('A reviewed implementation plan')

def test_research_reads_bounded_original_excerpts_from_vetted_tool_sources(monkeypatch):
    async def permitted(*args):return True
    monkeypatch.setattr(research,'allowed',permitted)
    html='<html><title>Retrieval guide</title><main><h1>Original retrieval guide</h1><p>'+('Retrieval indexes document chunks, checks permissions and retrieves evidence for the query. '*15)+'</p><p>'+('Evaluate retrieved evidence and answer correctness on representative held-out questions. '*15)+'</p></main></html>'
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,text=html,headers={'content-type':'text/html'}))) as client:
            return await research.read_source(client,'https://platform.openai.com/docs/guides/retrieval','retrieval document evidence evaluation',['OpenAI'])
    row=asyncio.run(run())
    assert row['source_kind']=='web_document' and row['title']=='Original retrieval guide'
    assert 'checks permissions' in row['excerpt'] and len(row['excerpt'])<=1800
    result=web_result();result['output'][1]['content'][0]['annotations']=[]
    assert len(research.source_urls(result))==2  # Tool-returned URLs can be read even when the synthesis omitted citations.

def test_research_respects_robots_and_rejects_redirects_outside_the_source_registry(monkeypatch):
    calls=[]
    async def permitted(*args):return True
    def redirect(request):calls.append(str(request.url));return httpx.Response(302,headers={'location':'http://127.0.0.1/private'})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(redirect)) as client:
            return await research.read_source(client,'https://platform.openai.com/docs/guide','query',[])
    monkeypatch.setattr(research,'allowed',permitted)
    assert asyncio.run(run()) is None and len(calls)==1
    async def denied(*args):return False
    monkeypatch.setattr(research,'allowed',denied)
    assert asyncio.run(run()) is None and len(calls)==1
