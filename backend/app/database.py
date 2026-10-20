from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Text, Integer, LargeBinary, ForeignKey, text,inspect,select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import DATABASE_URL,DATA

def now_iso():
    return datetime.now(timezone.utc).isoformat()

class Base(DeclarativeBase):
    pass

class Article(Base):
    __tablename__ = 'articles'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    url: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String)
    published_at: Mapped[str | None] = mapped_column(String, nullable=True)
    ingested_at: Mapped[str] = mapped_column(String, default=now_iso)
    excerpt: Mapped[str] = mapped_column(Text, default='')
    summary: Mapped[str] = mapped_column(Text, default='')
    why_it_matters: Mapped[str] = mapped_column(Text, default='')
    companies: Mapped[str] = mapped_column(Text, default='[]')
    topics: Mapped[str] = mapped_column(Text, default='[]')
    embedding: Mapped[str] = mapped_column(Text, default='[]')
    image: Mapped[str | None] = mapped_column(Text, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, default=1)
    classification: Mapped[str] = mapped_column(String, default='entities')
    summary_kind: Mapped[str] = mapped_column(String, default='source excerpt')

class Source(Base):
    __tablename__ = 'news_sources'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    config: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default='not checked')
    checked_at: Mapped[str | None] = mapped_column(String, nullable=True)
    detail: Mapped[str] = mapped_column(Text, default='')

class ArticlePassage(Base):
    __tablename__ = 'article_passages'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    article_id: Mapped[str] = mapped_column(ForeignKey('articles.id'), index=True)
    kind: Mapped[str] = mapped_column(String)
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[str] = mapped_column(Text, default='[]')

class ChatSession(Base):
    __tablename__ = 'chat_sessions'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[str] = mapped_column(String, default=now_iso)
    owner_id: Mapped[str] = mapped_column(String,default='local',server_default='local',index=True)

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('chat_sessions.id'))
    role: Mapped[str] = mapped_column(String)
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now_iso)

class Briefing(Base):
    __tablename__ = 'daily_briefings'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    date: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    timezone: Mapped[str] = mapped_column(String)
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now_iso)

class Preference(Base):
    __tablename__ = 'user_preferences'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[str] = mapped_column(Text)

class IngestionJob(Base):
    __tablename__ = 'ingestion_jobs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[str] = mapped_column(String, default=now_iso)
    finished_at: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[str] = mapped_column(Text, default='{}')

class Video(Base):
    __tablename__ = 'youtube_videos'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[str] = mapped_column(String, default=now_iso)

class YouTubeChannel(Base):
    __tablename__ = 'youtube_channels'
    company: Mapped[str] = mapped_column(String, primary_key=True)
    handle: Mapped[str] = mapped_column(String)
    channel_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, default='')
    uploads_playlist_id: Mapped[str] = mapped_column(String, default='')
    last_attempt_at: Mapped[str | None] = mapped_column(String, nullable=True)
    last_success_at: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default='not checked')
    detail: Mapped[str] = mapped_column(Text, default='')

class SchemaVersion(Base):
    __tablename__ = 'schema_versions'
    version: Mapped[int] = mapped_column(Integer, primary_key=True)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)

class Account(Base):
    __tablename__='accounts'
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),primary_key=True)
    email:Mapped[str]=mapped_column(String,unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(Text)
    language:Mapped[str]=mapped_column(String,default='en')
    created_at:Mapped[str]=mapped_column(String,default=now_iso)

class LoginSession(Base):
    __tablename__='login_sessions'
    token_hash:Mapped[str]=mapped_column(String,primary_key=True)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    expires_at:Mapped[str]=mapped_column(String)
    last_seen_at:Mapped[str]=mapped_column(String,default=now_iso)

class Membership(Base):
    __tablename__='memberships'
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),primary_key=True)
    plan:Mapped[str]=mapped_column(String,default='none')
    status:Mapped[str]=mapped_column(String,default='inactive')
    customer_id:Mapped[str|None]=mapped_column(String,nullable=True,unique=True)
    subscription_id:Mapped[str|None]=mapped_column(String,nullable=True,unique=True)
    pending_order:Mapped[str|None]=mapped_column(String,nullable=True)

class PaymentOrder(Base):
    __tablename__='payment_orders'
    id:Mapped[str]=mapped_column(String,primary_key=True)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    plan:Mapped[str]=mapped_column(String)
    method:Mapped[str]=mapped_column(String)
    provider_id:Mapped[str]=mapped_column(String,default='')
    url:Mapped[str]=mapped_column(Text,default='')
    status:Mapped[str]=mapped_column(String,default='creating')
    created_at:Mapped[str]=mapped_column(String,default=now_iso)

class BillingEvent(Base):
    __tablename__='billing_events'
    id:Mapped[str]=mapped_column(String,primary_key=True)
    created_at:Mapped[str]=mapped_column(String,default=now_iso)

class AudioGrant(Base):
    __tablename__='audio_grants'
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),primary_key=True)
    audio_id:Mapped[str]=mapped_column(String,primary_key=True)

class AudioCache(Base):
    __tablename__='audio_cache'
    id:Mapped[str]=mapped_column(String,primary_key=True)
    data:Mapped[bytes]=mapped_column(LargeBinary)

class SecurityBucket(Base):
    __tablename__='security_buckets'
    id:Mapped[str]=mapped_column(String,primary_key=True)
    events:Mapped[str]=mapped_column(Text,default='[]')
    updated_at:Mapped[str]=mapped_column(String,default=now_iso,index=True)

class JobLease(Base):
    __tablename__='job_leases'
    id:Mapped[str]=mapped_column(String,primary_key=True)
    owner:Mapped[str]=mapped_column(String)
    expires_at:Mapped[str]=mapped_column(String)

class Company(Base):
    __tablename__ = 'companies'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    color: Mapped[str] = mapped_column(String)

class CEOPersona(Base):
    __tablename__ = 'ceo_personas'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    company: Mapped[str] = mapped_column(ForeignKey('companies.id'))
    name: Mapped[str] = mapped_column(String)
    voice: Mapped[str] = mapped_column(String)

class ArticleCompany(Base):
    __tablename__ = 'article_companies'
    article_id: Mapped[str] = mapped_column(ForeignKey('articles.id'),primary_key=True)
    company: Mapped[str] = mapped_column(ForeignKey('companies.id'),primary_key=True)

class ArticleTopic(Base):
    __tablename__ = 'article_topics'
    article_id: Mapped[str] = mapped_column(ForeignKey('articles.id'),primary_key=True)
    topic: Mapped[str] = mapped_column(String,primary_key=True)

class BriefingArticle(Base):
    __tablename__ = 'briefing_articles'
    briefing_id: Mapped[str] = mapped_column(ForeignKey('daily_briefings.id'),primary_key=True)
    article_id: Mapped[str] = mapped_column(ForeignKey('articles.id'),primary_key=True)

class NotificationSetting(Base):
    __tablename__ = 'notification_settings'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'),primary_key=True)
    enabled: Mapped[int] = mapped_column(Integer,default=0)

engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False,'timeout':30} if DATABASE_URL.startswith('sqlite') else {'connect_timeout':15},
                       **({} if DATABASE_URL.startswith('sqlite') else {'pool_size':2,'max_overflow':2,'pool_pre_ping':True,'pool_recycle':240}))
Session = sessionmaker(engine, expire_on_commit=False)

def migrate():
    # WAL permits source reads while background indexing writes its cache.
    if DATABASE_URL.startswith('sqlite'):
        with engine.connect() as connection: connection.exec_driver_sql('PRAGMA journal_mode=WAL')
    # Additive migrations preserve the existing collection and conversations.
    Base.metadata.create_all(engine)
    if 'owner_id' not in {c['name'] for c in inspect(engine).get_columns('chat_sessions')}:
        with engine.begin() as connection:connection.execute(text("ALTER TABLE chat_sessions ADD COLUMN owner_id VARCHAR NOT NULL DEFAULT 'local'"))
    if 'last_seen_at' not in {c['name'] for c in inspect(engine).get_columns('login_sessions')}:
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE login_sessions ADD COLUMN last_seen_at VARCHAR'))
            connection.execute(text('UPDATE login_sessions SET last_seen_at=:now'),{'now':now_iso()})
    with Session.begin() as db:
        if DATABASE_URL.startswith('sqlite'):
            db.execute(text('BEGIN IMMEDIATE'))
        if not db.get(SchemaVersion, 1):
            db.add(SchemaVersion(version=1))
        if not db.get(SchemaVersion, 2):
            db.add(SchemaVersion(version=2))
        if not db.get(SchemaVersion, 3):
            db.add(SchemaVersion(version=3))
        if not db.get(SchemaVersion, 4):db.add(SchemaVersion(version=4))
        if not db.get(SchemaVersion, 6):db.add(SchemaVersion(version=6))
        if not db.get(SchemaVersion,5):
            # Preserve legacy owner audio only where no account already owns a grant.
            import re
            granted=set(db.scalars(select(AudioGrant.audio_id)).all())
            for path in (DATA/'audio').glob('*.mp3'):
                if re.fullmatch('[0-9a-f]{64}',path.stem) and path.stem not in granted:
                    db.add(AudioGrant(user_id='local',audio_id=path.stem))
            db.add(SchemaVersion(version=5))
        from .personas import PERSONAS
        if not db.get(User,'local'): db.add(User(id='local',name='Your newsroom'))
        for p in PERSONAS:
            if not db.get(Company,p['company']): db.add(Company(id=p['company'],color=p['color']))
        db.flush()
        for p in PERSONAS:
            if not db.get(CEOPersona,p['id']): db.add(CEOPersona(id=p['id'],company=p['company'],name=p['name'],voice=p['voice']))
        if not db.get(NotificationSetting,'local'): db.add(NotificationSetting(user_id='local',enabled=0))
        for a in db.query(Article).filter(Article.url.like('https://www.perplexity.ai/hub/blog/category/%')).all(): db.delete(a)
        db.flush()
        import json
        company_links=set(db.execute(select(ArticleCompany.article_id,ArticleCompany.company)).all())
        topic_links=set(db.execute(select(ArticleTopic.article_id,ArticleTopic.topic)).all())
        for a in db.query(Article).all():
            for c in json.loads(a.companies):
                if (a.id,c) not in company_links:
                    db.add(ArticleCompany(article_id=a.id,company=c));company_links.add((a.id,c))
            for t in json.loads(a.topics):
                if (a.id,t) not in topic_links:
                    db.add(ArticleTopic(article_id=a.id,topic=t));topic_links.add((a.id,t))
