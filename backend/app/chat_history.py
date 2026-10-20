"""Read saved local conversations without changing or regenerating their answers."""
import json
from sqlalchemy import select,func,case
from .database import Session,ChatSession,ChatMessage,Article,Video
from .article_views import article_json
from .personas import BY_ID
from .account_context import current_user

def list_chats(limit=100,offset=0):
    with Session() as db:
        groups=db.execute(select(ChatMessage.session_id,func.min(ChatMessage.id),func.max(ChatMessage.id),func.max(case((ChatMessage.role=='user',ChatMessage.id),else_=None)),func.count(ChatMessage.id)).join(ChatSession,ChatSession.id==ChatMessage.session_id).where(ChatSession.owner_id==current_user.get()).group_by(ChatMessage.session_id).order_by(func.max(ChatMessage.id).desc()).offset(offset).limit(limit)).all()
        ids={id for row in groups for id in [row[1],row[2],row[3]] if id is not None}
        messages={m.id:m for m in db.scalars(select(ChatMessage).where(ChatMessage.id.in_(ids))).all()}
        result=[]
        for session_id,first_id,last_id,last_user_id,count in groups:
            first=messages[first_id];last=messages[last_id]
            start=json.loads(first.payload);end=json.loads(last.payload)
            context=json.loads(messages[last_user_id].payload) if last_user_id else {}
            result.append({'id':session_id,'title':(start.get('article_title') or start.get('video_title') or start.get('text') or 'Newsroom conversation')[:140],'preview':end.get('text','')[:180],'created_at':first.created_at,'updated_at':last.created_at,'message_count':count,'presenter':end.get('presenter','newsroom'),'article_id':context.get('article_id'),'video_id':context.get('video_id')})
        return result

def load_chat(session_id):
    with Session() as db:
        owned=db.get(ChatSession,session_id)
        if not owned or owned.owner_id!=current_user.get():return None
        rows=db.scalars(select(ChatMessage).where(ChatMessage.session_id==session_id).order_by(ChatMessage.id)).all()
        messages=[{'role':m.role,**json.loads(m.payload),'created_at':m.created_at} for m in rows]
        context=next((m for m in reversed(messages) if m['role']=='user'),{})
        article=db.get(Article,context['article_id']) if context.get('article_id') else None
        video=db.get(Video,context['video_id']) if context.get('video_id') else None
        video_context=json.loads(video.payload) if video else None
        if context.get('video_id') and not video_context:
            # Keep the historical context available even if the upload cache expired.
            answer=next((m for m in messages if m.get('video_id')==context['video_id'] and m.get('presenter') in BY_ID),{})
            ceo=BY_ID.get(answer.get('presenter'),{})
            video_context={'id':context['video_id'],'title':context.get('video_title') or answer.get('video_title') or 'Previously discussed video','url':'https://www.youtube.com/watch?v='+context['video_id'],'company':ceo.get('company',''),'presenter':ceo.get('id','newsroom'),'channel':ceo.get('company',''),'thumbnail':'','published_at':''}
        return {'id':session_id,'messages':messages,'article_context':article_json(article) if article else None,'video_context':video_context,'topic':context.get('topic') or '', 'include_related':context.get('include_related',True),'missing_article':bool(context.get('article_id') and not article)}
