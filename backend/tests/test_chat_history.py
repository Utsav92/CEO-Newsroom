import json,uuid
from fastapi.testclient import TestClient
from app import services,chat_history,main
from app.database import ChatMessage,ChatSession,Article

def result(text='An answer.',**extra):
    return {'messages':[{'presenter':'sam_altman','text':text,'citations':[],**extra}]}

def test_saved_chat_list_uses_last_activity_and_keeps_each_conversation(db):
    first=services.save_chat_result('First conversation',None,result())['session_id']
    second=services.save_chat_result('Another conversation',None,result())['session_id']
    services.save_chat_result('Continue the first',first,result('A continued answer.'))
    rows=chat_history.list_chats()
    assert [r['id'] for r in rows]==[first,second]
    assert rows[0]['title']=='First conversation' and rows[0]['preview']=='A continued answer.'
    assert rows[0]['message_count']==4 and rows[1]['message_count']==2
    assert len(chat_history.list_chats(1))==1
    assert chat_history.list_chats(1,1)[0]['id']==second
    assert chat_history.list_chats(1,2)==[]

def test_reopening_article_chat_restores_scope_topic_sources_and_followups(db,seed):
    seed()
    followups={'follow_up_question':'Which goal matters most?','reply_options':['Costs','Reliability'],'suggested_questions':['What is the next step?','Which risks matter?']}
    saved=services.save_chat_result('Explain this article.',None,result(article_id='report-1',**followups),{'article_id':'report-1','article_title':'Saved article title','topic':'Reliability','include_related':False})
    data=chat_history.load_chat(saved['session_id'])
    assert data['article_context']['id']=='report-1'
    assert data['topic']=='Reliability' and data['include_related'] is False
    assert data['messages'][1]['reply_options']==followups['reply_options']
    assert data['messages'][0]['role']=='user'
    assert chat_history.list_chats()[0]['title']=='Saved article title'
    assert chat_history.load_chat(saved['session_id'])==data
    with db() as s:assert s.query(ChatMessage).count()==2

def test_expired_video_metadata_does_not_remove_the_saved_conversation(db):
    saved=services.save_chat_result('Explain the video.',None,result(video_id='fixture0000',video_title='An official upload'),{'video_id':'fixture0000','video_title':'An official upload'})
    data=chat_history.load_chat(saved['session_id'])
    assert data['video_context']['id']=='fixture0000'
    assert data['video_context']['company']=='OpenAI'
    assert data['video_context']['url']=='https://www.youtube.com/watch?v=fixture0000'
    assert len(data['messages'])==2

def test_missing_article_keeps_saved_messages_available(db):
    saved=services.save_chat_result('Explain the old story.',None,result(),{'article_id':'missing-old','article_title':'Historical story'})
    data=chat_history.load_chat(saved['session_id'])
    assert data['missing_article'] and data['article_context'] is None
    assert len(data['messages'])==2

def test_saved_chat_api_lists_reopens_and_validates_identifiers_without_writes(db):
    saved=services.save_chat_result('A saved conversation',None,result())
    with TestClient(main.app) as client:
        listed=client.get('/api/chat/sessions?limit=1')
        assert listed.status_code==200 and listed.json()['sessions'][0]['id']==saved['session_id']
        detail=client.get('/api/chat/sessions/'+saved['session_id'])
        assert detail.status_code==200 and detail.json()['messages'][0]['text']=='A saved conversation'
        assert client.get('/api/chat/sessions/'+str(uuid.uuid4())).status_code==404
        assert client.get('/api/chat/sessions/not-a-session').status_code==422
    with db() as s:assert s.query(ChatSession).count()==1 and s.query(ChatMessage).count()==2
