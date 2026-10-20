import sys, json
from pathlib import Path
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import database, services, ingestion, main, rag, youtube, video_rag, ai, chat_history, accounts,billing
from app.database import Base, Article

@pytest.fixture
def db(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session=sessionmaker(engine,expire_on_commit=False)
    for module in [database,services,ingestion,main,rag,youtube,video_rag,chat_history,accounts,billing]: monkeypatch.setattr(module,'Session',session)
    monkeypatch.setattr(main,'ADMIN_TOKEN','')
    monkeypatch.setattr(main,'AUTH_REQUIRED',False)
    monkeypatch.setattr(main,'PUBLIC_APP_URL','http://testserver')
    monkeypatch.setattr(main,'PROXY_SECRET','')
    accounts.attempts.clear()
    monkeypatch.setattr(ai,'OPENAI_KEY','')
    monkeypatch.setattr(main,'YOUTUBE_KEY','')
    async def no_initial_ingestion():pass
    monkeypatch.setattr(main,'initial_ingestion',no_initial_ingestion)
    main.request_limits.clear()
    yield session
    engine.dispose()

@pytest.fixture
def seed(db):
    def add(id='report-1',company='OpenAI',title='OpenAI publishes research',published=None,embedding=None,url=None):
        with db.begin() as session:
            row=Article(id=id,url=url or 'https://example.org/'+id,title=title,source='Test publisher',published_at=published or datetime.now(timezone.utc).isoformat(),excerpt='A test source excerpt, not a real news report.',summary='A test source excerpt, not a real news report.',companies=json.dumps([company] if company else []),topics='["AI research"]',embedding=json.dumps(embedding or [1,0]))
            session.add(row)
        return id
    return add
