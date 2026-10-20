import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app import main, accounts

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('prepare_vercel', ROOT / 'scripts' / 'prepare_vercel.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
SECRET = 'a' * 64


@pytest.fixture
def cloud(db, monkeypatch):
    monkeypatch.setattr(main, 'PROXY_SECRET', SECRET)
    monkeypatch.setattr(main, 'PUBLIC_APP_URL', 'https://newsroom.vercel.app')
    monkeypatch.setattr(main, 'AUTH_REQUIRED', True)
    monkeypatch.setattr(accounts, 'ALLOW_REMOTE_REGISTRATION', False)
    return TestClient(main.app, base_url='http://backend.onrender.com', client=('10.0.0.1', 4000))


def ingress(**extra):
    return {'X-Newsroom-Origin-Secret': SECRET, 'X-Real-IP': '8.8.8.8', **extra}


def test_direct_backend_rejects_spoofed_forwarding_and_untrusted_secrets(cloud):
    assert cloud.get('/api/auth/session', headers={'X-Forwarded-Proto': 'https',
        'X-Forwarded-Host': 'newsroom.vercel.app'}).status_code == 403
    assert cloud.get('/api/session', headers=ingress(**{'X-Newsroom-Origin-Secret': 'wrong'})).status_code == 403
    duplicate = [('x-newsroom-origin-secret', SECRET), ('x-newsroom-origin-secret', SECRET), ('x-real-ip', '8.8.8.8')]
    assert cloud.get('/api/session', headers=duplicate).status_code == 403


def test_authenticated_ingress_keeps_secure_cookie_and_private_api_policy(cloud):
    response = cloud.get('/api/session', headers=ingress(**{'X-Forwarded-Host': 'attacker.example'}))
    assert response.status_code == 200
    assert 'Secure' in response.headers['set-cookie'] and 'HttpOnly' in response.headers['set-cookie']
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-frame-options'] == 'DENY'
    assert cloud.get('/api/news', headers=ingress()).status_code == 401
    assert cloud.get('/api/auth/session', headers=ingress(**{'Sec-Fetch-Site': 'cross-site'})).status_code == 403


def test_proxy_cannot_use_loopback_identity_to_claim_first_owner(cloud, monkeypatch):
    monkeypatch.setattr(accounts, 'ALLOW_REMOTE_REGISTRATION', True)
    for address in ('127.0.0.1', '::1', '10.0.0.2', 'not-an-ip', ''):
        assert cloud.get('/api/session', headers=ingress(**{'X-Real-IP': address})).status_code == 403
    assert cloud.get('/api/auth/session', headers=ingress()).json()['first_run']


def test_health_probe_reveals_only_readiness(cloud):
    response = cloud.get('/healthz')
    assert response.status_code == 200 and response.json() == {'status': 'ok'}
    assert response.headers['cache-control'] == 'no-store'
    assert cloud.post('/healthz').status_code == 403
    assert cloud.get('/api/health').status_code == 403


def test_cloud_login_csrf_and_logout_preserve_same_origin_protection(cloud, monkeypatch):
    from starlette.requests import Request
    from starlette.responses import Response
    monkeypatch.setattr(accounts, 'SCRYPT_N', 1024)
    local = Request({'type': 'http', 'method': 'POST', 'scheme': 'http',
        'path': '/', 'headers': [(b'host', b'localhost')], 'query_string': b'',
        'client': ('127.0.0.1', 0), 'server': ('localhost', 80)})
    accounts.register(local, Response(), 'Owner', 'owner@example.test', 'Cloud test password 123')
    browser = TestClient(main.app, base_url='https://newsroom.vercel.app')

    def csrf():
        return ingress(**{'X-Newsroom-Token': browser.get('/api/session', headers=ingress()).json()['token'],
                          'Origin': 'https://newsroom.vercel.app'})

    result = browser.post('/api/auth/login', headers=csrf(),
        json={'email': 'owner@example.test', 'password': 'Cloud test password 123'})
    assert result.status_code == 200 and 'Secure' in result.headers['set-cookie']
    assert browser.get('/api/news', headers=ingress()).status_code == 200
    assert browser.put('/api/auth/profile', headers=ingress(), json={'name': 'No CSRF'}).status_code == 403
    assert browser.put('/api/auth/profile', headers=csrf(), json={'name': 'Cloud owner'}).status_code == 200
    forged = csrf(); forged['Origin'] = 'https://attacker.example'
    assert browser.put('/api/auth/profile', headers=forged, json={'name': 'Bad origin'}).status_code == 403
    assert browser.post('/api/auth/logout', headers=csrf(), json={}).status_code == 200
    assert browser.get('/api/news', headers=ingress()).status_code == 401


@pytest.mark.parametrize('url', [
    'http://backend.onrender.com', 'https://127.0.0.1', 'https://[::1]',
    'https://localhost', 'https://server.local', 'https://server.test',
    'https://user:password@api.example.com', 'https://api.example.com/path',
    'https://api.example.com?key=secret', 'https://api.example.com:444',
])
def test_vercel_preparation_rejects_unsafe_backend_addresses(url):
    with pytest.raises(ValueError):
        prepare.configuration(url)


def test_vercel_routes_preserve_api_audio_and_assets_without_publishing_credentials():
    config = prepare.configuration('https://newsroom-api.onrender.com/')
    route = config['routes'][0]
    assert route['src'] == '/(.*)' and route['dest'] == 'https://newsroom-api.onrender.com/$1'
    assert route['headers']['Cache-Control'] == 'private, no-store'
    assert route['transforms'][0]['args'] == '$NEWSROOM_PROXY_SECRET'
    assert 'env' not in config and 'build' not in config
