import asyncio,json
import pytest
from fastapi.testclient import TestClient
from app import services,main
from app.conversation import follow_up_fields
from app.database import ChatMessage

INTERACTIVE={'follow_up_question':'Are you deciding as a parent or as an app developer?','reply_options':['As a parent','As an app developer'],'suggested_questions':['Which safeguards should be prioritized?','How can the options be compared?']}

def test_contextual_questions_are_returned_and_persisted_without_an_extra_call(db,seed,monkeypatch):
    seed();calls=[]
    async def embed(texts):return [[1,0]]
    async def generate(instructions,context,schema,name):
        calls.append(name)
        assert 'do not ask again' in instructions
        assert set(INTERACTIVE)<=set(schema['properties']['messages']['items']['required'])
        return {'messages':[{'presenter':'sam_altman','text':'An assessment of the situation.','answer_kind':'analysis','article_ids':['report-1'],**INTERACTIVE}]}
    monkeypatch.setattr(services,'embed',embed);monkeypatch.setattr(services,'structured',generate)
    result=asyncio.run(services.chat('What are the risks for OpenAI?'))
    assert len(calls)==1
    assert all(result['messages'][0][key]==value for key,value in INTERACTIVE.items())
    with db() as s:
        message=json.loads(s.query(ChatMessage).filter_by(role='assistant').one().payload)
        assert message['follow_up_question']==INTERACTIVE['follow_up_question']
        assert message['suggested_questions']==INTERACTIVE['suggested_questions']

@pytest.mark.parametrize('question,clicked',[('As a parent',False),('What could OpenAI do next?',True)])
def test_clarifying_answers_and_clicked_questions_keep_the_original_story(db,seed,monkeypatch,question,clicked):
    seed('old-report',title='OpenAI safety concerns',published='2020-01-01T12:00:00+00:00')
    source=services.articles()[0]
    saved=services.save_chat_result('Explain the concern.',None,{'messages':[{'presenter':'sam_altman','text':'An assessment.','citations':[source],**INTERACTIVE}]})
    async def generate(instructions,context,schema,name):
        assert context['evidence'][0]['id']=='old-report'
        assert context['history'][-1]['follow_up_question']==INTERACTIVE['follow_up_question']
        return {'messages':[{'presenter':'sam_altman','text':'A parent could compare safeguards and choose a practical next step.','answer_kind':'analysis','article_ids':['old-report'],**INTERACTIVE}]}
    monkeypatch.setattr(services,'structured',generate)
    with TestClient(main.app) as client:
        token=client.get('/api/session').json()['token']
        response=client.post('/api/chat',headers={'X-Newsroom-Token':token},json={'question':question,'session_id':saved['session_id'],'presenter':'sam_altman','period':'today','follow_up':clicked})
    assert response.status_code==200
    result=response.json()['messages'][0]
    assert result['presenter']=='sam_altman' and result['citations'][0]['id']=='old-report'

def test_bad_suggestions_fall_back_without_losing_the_answer():
    fields=follow_up_fields({'follow_up_question':None,'reply_options':['Same','same',42],'suggested_questions':'bad'},'NVIDIA')
    assert 'NVIDIA' in fields['follow_up_question']
    assert len(fields['reply_options'])>=2 and len(fields['suggested_questions'])>=2
    clean=follow_up_fields({'follow_up_question':'  Which\n constraint matters? ','reply_options':['Price','price','Speed'],'suggested_questions':['What next?','Which evidence?']})
    assert clean['follow_up_question']=='Which constraint matters?'
    assert clean['reply_options']==['Price','Speed']
