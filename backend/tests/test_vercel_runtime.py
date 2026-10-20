import asyncio
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app import main,serverless
from app.database import AudioCache,AudioGrant,SchemaVersion,User


def test_vercel_lifespan_checks_durable_schema_without_starting_scheduler(db,monkeypatch):
    monkeypatch.setattr(main,'SERVERLESS',True)
    monkeypatch.setattr(main,'CSRF_KEY','s'*64);monkeypatch.setattr(main,'CRON_SECRET','c'*64)
    with db.begin() as session:session.add(SchemaVersion(version=6))
    with TestClient(main.app) as client:
        assert not main.scheduler.running
        assert client.get('/api/session').status_code==200


def test_cron_authentication_precedes_shared_work(db,monkeypatch):
    monkeypatch.setattr(main,'CRON_SECRET','c'*64)
    calls=[]
    async def work():calls.append(True);return {'status':'complete','added':2}
    monkeypatch.setattr(main,'ingest',work)
    monkeypatch.setattr(main,'generate_briefing',lambda *args:None)
    monkeypatch.setattr(serverless,'cleanup_limits',lambda:None)
    client=TestClient(main.app)
    assert client.get('/api/cron/news').status_code==401
    assert client.get('/api/cron/news',headers={'Authorization':'Bearer wrong'}).status_code==401
    assert not calls
    assert client.get('/api/cron/news',headers={'Authorization':'Bearer '+'c'*64}).json()['added']==2
    assert calls==[True]


def test_durable_audio_cache_is_private_and_survives_local_file_absence(db,monkeypatch):
    monkeypatch.setattr(main,'SERVERLESS',True)
    monkeypatch.setattr(main,'AUTH_REQUIRED',True)
    id='f'*64
    with db.begin() as session:
        session.add(User(id='local',name='Owner'));session.add(AudioCache(id=id,data=b'private narration'))
    monkeypatch.setattr(main.accounts,'session_user',lambda request:{'id':'local','name':'Owner','language':'en'})
    client=TestClient(main.app)
    assert client.get('/api/audio/'+id).status_code==404
    with db.begin() as session:session.add(AudioGrant(user_id='local',audio_id=id))
    result=client.get('/api/audio/'+id)
    assert result.status_code==200 and result.content==b'private narration'
    assert result.headers['cache-control']=='no-store'


def test_cloud_audio_reuses_private_cache_without_provider_or_filesystem(db,monkeypatch):
    monkeypatch.setattr(serverless,'Session',db)
    with db.begin() as session:session.add(AudioCache(id='a'*64,data=b'cached'))
    async def forbidden():raise AssertionError('A cached narration must not call the provider')
    asyncio.run(serverless.cloud_audio('a'*64,forbidden))


def test_cloud_audio_rejects_payload_over_function_limit(db,monkeypatch):
    monkeypatch.setattr(serverless,'Session',db)
    async def large():return b'x'*3_500_001
    with pytest.raises(HTTPException) as error:asyncio.run(serverless.cloud_audio('a'*64,large))
    assert error.value.status_code==413


def test_exact_deployment_origin_is_allowed_but_arbitrary_host_is_rejected(db,monkeypatch):
    monkeypatch.setattr(main,'DEPLOYMENT_ORIGIN','https://newsroom-build.vercel.app')
    client=TestClient(main.app,base_url='https://newsroom-build.vercel.app')
    assert client.get('/api/session').status_code==200
    assert client.get('/api/session',headers={'Host':'attacker.example'}).status_code==403
