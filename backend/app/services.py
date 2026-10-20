import json, uuid, re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select
from .database import Session, Article, Preference, ChatSession, ChatMessage, Briefing, BriefingArticle, Video, now_iso
from .personas import BY_COMPANY, BY_ID
from .ai import embed, similarity, entities, structured, AIUnavailable
from .config import TIMEZONE, YOUTUBE_KEY
from .article_views import article_json
from .rag import explain_article, explain_company_topic
from .youtube import youtube as official_youtube, cached_videos
from .video_rag import explain_video
from .answers import answer_question
from .account_context import current_user,current_language
from fastapi import HTTPException
from .research import research_sources,attach_research

DEFAULT_PREFS = dict(companies=[],topics=[],saved=[],personalization=False,timezone=TIMEZONE,briefing_time='08:00',evening_time='18:00',notifications=False,autoplay=False,voice='presenter',speed=1.0)

def preferences():
    with Session() as db:
        p=db.get(Preference,current_user.get())
        return {**DEFAULT_PREFS,**(json.loads(p.payload) if p else {})}

def since_date(period,tz):
    now=datetime.now(ZoneInfo(tz))
    if period=='today': return now.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
    if period=='week': return (now-timedelta(days=7)).astimezone(timezone.utc)
    if period=='month': return (now-timedelta(days=30)).astimezone(timezone.utc)
    return None

def publication_instant(value):
    d=datetime.fromisoformat(value)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

def articles(company=None,topic=None,q='',period='all',saved=False,limit=100):
    prefs=preferences(); since=since_date(period,prefs['timezone'])
    with Session() as db:
        query=select(Article)
        # Saved items remain reachable even after 1,000 newer feed items arrive.
        if saved:query=query.where(Article.id.in_(prefs['saved']))
        rows=db.scalars(query.order_by(Article.published_at.desc(),Article.ingested_at.desc()).limit(1000)).all()
        result=[]
        for a in rows:
            data=article_json(a)
            if company and company not in data['companies']: continue
            if topic and topic not in data['topics']: continue
            if q and q.lower() not in (a.title+' '+a.summary+' '+' '.join(data['companies'])).lower(): continue
            if since:
                if not a.published_at: continue
                if len(a.published_at)==10:
                    if datetime.fromisoformat(a.published_at).date()<since.astimezone(ZoneInfo(prefs['timezone'])).date(): continue
                elif publication_instant(a.published_at)<since: continue
            if saved and a.id not in prefs['saved']: continue
            result.append(data)
    if prefs['personalization']:
        # Explicit company/topic preferences and saved-story semantic similarity.
        with Session() as db:
            saved_vectors=[json.loads(a.embedding) for a in db.scalars(select(Article).where(Article.id.in_(prefs['saved']))).all()]
            vectors={a.id:json.loads(a.embedding) for a in db.scalars(select(Article)).all()}
        def rank(a):
            days=(datetime.now(timezone.utc)-publication_instant(a['published_at'])).total_seconds()/86400 if a['published_at'] else 100
            return 5/(1+max(0,days)) + 2*len(set(a['companies']) & set(prefs['companies'])) + len(set(a['topics']) & set(prefs['topics'])) + max([similarity(vectors.get(a['id'],[]),v) for v in saved_vectors] or [0])
        result.sort(key=rank,reverse=True)
    return result[:limit]

def save_chat_result(question,session_id,result,context=None):
    session_id=session_id or str(uuid.uuid4())
    with Session.begin() as db:
        existing=db.get(ChatSession,session_id)
        if existing and existing.owner_id!=current_user.get():raise HTTPException(404,'Conversation not found.')
        if not existing:db.add(ChatSession(id=session_id,owner_id=current_user.get()));db.flush()
        db.add(ChatMessage(session_id=session_id,role='user',payload=json.dumps({'text':question,**(context or {})})))
        for msg in result['messages']:
            msg['language']=current_language.get()
            db.add(ChatMessage(session_id=session_id,role='assistant',payload=json.dumps(msg)))
    return {**result,'session_id':session_id}

async def chat(question,session_id=None,presenter=None,period='all',article_id=None,topic=None,include_related=True,video_id=None,follow_up=False):
    if session_id:
        with Session() as db:
            owned=db.get(ChatSession,session_id)
            if not owned or owned.owner_id!=current_user.get():raise HTTPException(404,'Conversation not found.')
    prefs=preferences()
    # Explicit date intent takes precedence over a broader UI period.
    if re.search(r'\btoday\b',question,re.I): period='today'
    elif re.search(r'\b(this week|past week|last week)\b',question,re.I): period='week'
    elif re.search(r'\b(this month|past month)\b',question,re.I): period='month'
    candidates=articles(period=period,limit=250)
    targets=entities(question)
    if presenter in BY_ID and not targets: targets=[BY_ID[presenter]['company']]
    if targets: candidates=[a for a in candidates if set(a['companies']) & set(targets)]
    history=[]
    if session_id:
        with Session() as db:
            history=[json.loads(m.payload) for m in db.scalars(select(ChatMessage).where(ChatMessage.session_id==session_id).order_by(ChatMessage.id.desc()).limit(6)).all()][::-1]
    latest_answer=next((m for m in reversed(history) if 'presenter' in m),{})
    follow_up=bool(follow_up or (not entities(question) and (latest_answer.get('follow_up_question') or re.search(r'\b(that|this|it|those|these|they|their|more|why)\b|\bwhat about\b',question,re.I))))
    if not entities(question) and follow_up:
        previous=[]
        for message in reversed(history):
            if 'presenter' not in message: break
            if message['presenter'] in BY_ID: previous.append(BY_ID[message['presenter']]['company'])
        if previous:
            targets=[BY_ID[presenter]['company']] if presenter in BY_ID else list(dict.fromkeys(reversed(previous)))
            candidates=[a for a in articles(period=period,limit=250) if set(a['companies']) & set(targets)]
    if video_id:
        result=await explain_video(video_id,question,topic,include_related,history)
        return save_chat_result(question,session_id,result,{'video_id':video_id,'video_title':result['video_context']['title'],'topic':topic,'include_related':include_related})
    if article_id:
        result=await explain_article(article_id,question,topic,presenter,include_related,history)
        return save_chat_result(question,session_id,result,{'article_id':article_id,'article_title':result['article_context']['title'],'topic':topic,'include_related':include_related})
    sources=[]
    # Preserve the actual referenced reporting across vague follow-ups. Rehydrate
    # from the database, so old generated citations never become evidence.
    if follow_up:
        previous_ids=[]
        for message in reversed(history):
            if 'presenter' not in message:break
            previous_ids.extend(a.get('id') for a in message.get('citations',[]) if isinstance(a,dict))
            if message.get('article_id'):previous_ids.append(message['article_id'])
        with Session() as db:
            for id in dict.fromkeys(previous_ids):
                record=db.get(Article,id) if id else None
                if record:
                    item=article_json(record)
                    if not targets or set(item['companies']) & set(targets):sources.append(item)
                if len(sources)>=4:break
    if candidates:
        query_vector=(await embed([question+' '+ ' '.join(a['title'] for a in sources)]))[0]
        with Session() as db:
            vectors={a.id:json.loads(a.embedding) for a in db.scalars(select(Article).where(Article.id.in_([a['id'] for a in candidates]))).all()}
        words=set(re.findall(r'\w+',question.lower()))-{'the','what','is','in','at','of','and','a','today','this','week'}
        def score(a):
            lexical=len(words & set(re.findall(r'\w+',(a['title']+' '+a['excerpt']).lower())))/max(1,len(words))
            return .75*similarity(query_vector,vectors.get(a['id'],[]))+.25*lexical
        candidates.sort(key=score,reverse=True)
        # Preserve both sides of a comparison in the bounded context.
        for target in targets:
            first=next((a for a in candidates if target in a['companies']),None)
            if first and first not in sources: sources.append(first)
        sources.extend(a for a in candidates if a not in sources)
        sources=sources[:10]
    web,research=await research_sources(question,sources,targets,history,topic=topic)
    sources.extend(a for a in web if a['url'] not in {s['url'] for s in sources})
    if len(targets)>1:
        result=await explain_company_topic(question,targets,sources,history)
        return save_chat_result(question,session_id,attach_research(result,research))
    result=await answer_question(question,sources,targets,history,{'timezone':prefs['timezone'],'current_date':datetime.now(ZoneInfo(prefs['timezone'])).isoformat(),'selected_presenter':presenter,'research':research},generator=structured)
    return save_chat_result(question,session_id,attach_research({**result,'retrieval_count':len(sources)},research))


def generate_briefing(kind='morning',company=None):
    prefs=preferences(); local=datetime.now(ZoneInfo(prefs['timezone'])); period='week' if kind=='weekly' else 'today'
    rows=articles(company=company,period=period,limit=100)
    rows.sort(key=lambda a:(a['significance'],a['published_at'] or ''),reverse=True)
    selected=[]; counts={}
    for row in rows:
        c=next(iter(row['companies']),'newsroom')
        if counts.get(c,0)>=2: continue
        counts[c]=counts.get(c,0)+1; selected.append(row)
        if len(selected)>=8: break
    related=cached_videos()[:30]
    selected_companies={c for a in selected for c in a['companies']}
    related=[v for v in related if v['company'] in selected_companies][:4]
    payload={'date':local.date().isoformat(),'kind':kind,'timezone':prefs['timezone'],'articles':selected,'videos':related,'messages':[{'presenter':a['presenters'][0] if a['presenters'] else 'newsroom','text':a['summary'],'citations':[a]} for a in selected],'empty':not selected,'generated_at':now_iso()}
    id=f'{local.date()}-{kind}-{company or "all"}'
    with Session.begin() as db:
        row=db.get(Briefing,id)
        if row: row.payload=json.dumps(payload)
        else: db.add(Briefing(id=id,date=str(local.date()),kind=kind,timezone=prefs['timezone'],payload=json.dumps(payload)))
        db.flush()
        db.query(BriefingArticle).filter_by(briefing_id=id).delete()
        for a in selected: db.add(BriefingArticle(briefing_id=id,article_id=a['id']))
    return {**payload,'id':id}

async def youtube(company='OpenAI',q=''):
    return await official_youtube(company,q,key=YOUTUBE_KEY,tz=preferences()['timezone'] if YOUTUBE_KEY else TIMEZONE)
