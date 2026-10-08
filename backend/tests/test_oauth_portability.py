"""OAuth portability/security contracts. Google is always mocked."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from http.cookies import SimpleCookie
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, update

from app.api.routes import auth
from app.main import app
from app.security.session import oauth_cookie_name, token_digest
from app.storage import models as dbm
from app.storage.database import Repository, repository
from test_google_auth_api import isolated_auth_db, google_settings, begin_login

PUBLIC = 'https://ai-agent-environment-simulator.vercel.app'
CALLBACK = '/api/v1/auth/google/callback'

@pytest.fixture
def production_settings(google_settings):
    with patch.object(auth.settings, 'FRONTEND_URL', PUBLIC), patch.object(auth.settings, 'GOOGLE_REDIRECT_URI', PUBLIC + CALLBACK):
        yield

def complete(client, query):
    return client.get(CALLBACK, params={'state': query['state'][0], 'code': 'mock-code'}, follow_redirects=False)

def claims(query, identity='fresh'):
    return dict(sub=identity, email=f'{identity}@example.com', email_verified=True, name=identity, nonce=query['nonce'][0])

def test_fresh_browser_logout_relogin(isolated_auth_db, production_settings):
    with TestClient(app, base_url=PUBLIC) as client, patch.object(auth, '_exchange_code', AsyncMock(return_value={'id_token': 'mock'})), patch.object(auth, '_verify_google_id_token') as verify:
        assert client.get('/api/v1/auth/me').status_code == 401
        for _ in range(2):
            _, query = begin_login(client)
            verify.return_value = claims(query)
            assert complete(client, query).status_code == 302
            me = client.get('/api/v1/auth/me')
            assert me.status_code == 200 and me.json()['workspace']['kind'] == 'personal'
            assert client.post('/api/v1/auth/logout', headers={'Origin': PUBLIC}).status_code == 204
            assert client.get('/api/v1/auth/me').status_code == 401

@pytest.mark.parametrize('failure', ['missing_state', 'wrong_state', 'missing_cookie', 'no_transaction', 'expired', 'tampered_cookie'])
def test_invalid_transaction_never_calls_google(isolated_auth_db, google_settings, failure):
    with TestClient(app) as client, patch.object(auth, '_exchange_code', AsyncMock()) as exchange:
        _, query = begin_login(client)
        state = query['state'][0]
        name = oauth_cookie_name(state)
        params = {'state': state, 'code': 'mock'}
        if failure == 'missing_state':
            params.pop('state')
        elif failure == 'wrong_state':
            params['state'] = 'wrong'
        elif failure == 'missing_cookie':
            client.cookies.clear()
        elif failure == 'no_transaction':
            assert repository.consume_oauth_transaction(state_digest=token_digest(state), cookie_digest=token_digest(client.cookies.get(name)), now=auth.utcnow().isoformat())
        elif failure == 'expired':
            with repository.engine.begin() as connection:
                connection.execute(update(dbm.oauth_transactions).values(expires_at=(auth.utcnow() - timedelta(seconds=1)).isoformat()))
        else:
            client.cookies.clear()
            client.cookies.set(name, json.dumps(['injected', 'verifier']), path=CALLBACK)
        response = client.get(CALLBACK, params=params, follow_redirects=False)
        assert response.status_code == 400 and response.json()['detail']['code'] == 'invalid_oauth_state'
        exchange.assert_not_awaited()

def test_replay_with_original_cookie_rejected(isolated_auth_db, google_settings):
    with TestClient(app) as client, patch.object(auth, '_exchange_code', AsyncMock(return_value={'id_token': 'mock'})) as exchange, patch.object(auth, '_verify_google_id_token') as verify:
        _, query = begin_login(client)
        name = oauth_cookie_name(query['state'][0])
        cookie = client.cookies.get(name)
        verify.return_value = claims(query)
        assert complete(client, query).status_code == 302
        client.cookies.set(name, cookie, path=CALLBACK)
        assert complete(client, query).status_code == 400
        exchange.assert_awaited_once()

def test_two_tabs_preserve_pending_logins(isolated_auth_db, google_settings):
    with TestClient(app) as client, patch.object(auth, '_exchange_code', AsyncMock(return_value={'id_token': 'mock'})), patch.object(auth, '_verify_google_id_token') as verify:
        _, first = begin_login(client)
        _, second = begin_login(client)
        assert first['state'] != second['state']
        for query in (first, second):
            verify.return_value = claims(query)
            assert complete(client, query).status_code == 302

def test_devices_isolated_and_cookie_substitution_rejected(isolated_auth_db, google_settings):
    with TestClient(app) as first, TestClient(app) as second, patch.object(auth, '_exchange_code', AsyncMock(return_value={'id_token': 'mock'})) as exchange, patch.object(auth, '_verify_google_id_token') as verify:
        _, a = begin_login(first)
        _, b = begin_login(second)
        assert complete(second, a).status_code == 400
        assert complete(first, b).status_code == 400
        second.cookies.set(oauth_cookie_name(a['state'][0]), second.cookies.get(oauth_cookie_name(b['state'][0])), path=CALLBACK)
        assert complete(second, a).status_code == 400
        exchange.assert_not_awaited()
        for client, query, identity in ((first, a, 'a'), (second, b, 'b')):
            verify.return_value = claims(query, identity)
            assert complete(client, query).status_code == 302
            assert client.get('/api/v1/auth/me').json()['user']['email'] == f'{identity}@example.com'

def test_restart_changed_ip_and_restored_browser_cookies(isolated_auth_db, google_settings):
    with TestClient(app) as client, patch.object(auth, '_exchange_code', AsyncMock(return_value={'id_token': 'mock'})), patch.object(auth, '_verify_google_id_token') as verify:
        _, query = begin_login(client)
        cookie = client.cookies.get(oauth_cookie_name(query['state'][0]))
        repository.engine.dispose()
        repository._engine = repository._engine_url = None
        repository.initialize()
        client.cookies.clear()
        client.cookies.set(oauth_cookie_name(query['state'][0]), cookie, path=CALLBACK)
        verify.return_value = claims(query)
        response = client.get(CALLBACK, params={'state': query['state'][0], 'code': 'mock'}, headers={'X-Forwarded-For': '203.0.113.20'}, follow_redirects=False)
        assert response.status_code == 302

def test_https_cookie_attributes_ignore_untrusted_proxy_headers(isolated_auth_db, production_settings):
    with TestClient(app, base_url=PUBLIC) as client, patch.object(auth, '_exchange_code', AsyncMock(return_value={'id_token': 'mock'})), patch.object(auth, '_verify_google_id_token') as verify:
        response = client.get('/api/v1/auth/google/login', headers={'Host': 'railway.internal', 'X-Forwarded-Host': 'attacker.example', 'X-Forwarded-Proto': 'http'}, follow_redirects=False)
        query = parse_qs(urlsplit(response.headers['location']).query)
        assert query['redirect_uri'] == [PUBLIC + CALLBACK]
        jar = SimpleCookie(); jar.load(response.headers['set-cookie'])
        cookie = jar[oauth_cookie_name(query['state'][0])]
        assert cookie['secure'] and cookie['httponly'] and not cookie['domain']
        assert cookie['samesite'] == 'lax' and cookie['path'] == CALLBACK and cookie['max-age'] == '600'
        verify.return_value = claims(query)
        jar = SimpleCookie()
        for header in complete(client, query).headers.get_list('set-cookie'):
            jar.load(header)
        cookie = jar['app_session']
        assert cookie['secure'] and cookie['httponly'] and not cookie['domain']
        assert cookie['samesite'] == 'lax' and cookie['path'] == '/' and cookie['max-age'] == '43200'
        assert jar[oauth_cookie_name(query['state'][0])]['max-age'] == '0'

@pytest.mark.parametrize('callback', ['https://backend.invalid/api/v1/auth/google/callback', 'http://ai-agent-environment-simulator.vercel.app/api/v1/auth/google/callback', PUBLIC + '/wrong', PUBLIC + CALLBACK + '?extra=1'])
def test_bad_public_callback_fails_before_redirect(isolated_auth_db, production_settings, callback):
    with patch.object(auth.settings, 'GOOGLE_REDIRECT_URI', callback), TestClient(app) as client:
        response = client.get('/api/v1/auth/google/login', follow_redirects=False)
        assert response.status_code == 503 and response.json()['detail']['code'] == 'oauth_origin_mismatch'
        assert 'set-cookie' not in response.headers

@pytest.mark.parametrize('path,method', [('/api/v1/auth/google/login', 'get'), (CALLBACK, 'get'), ('/api/v1/auth/me', 'get'), ('/api/v1/auth/logout', 'post')])
def test_auth_responses_never_cached(isolated_auth_db, google_settings, path, method):
    with TestClient(app) as client:
        response = getattr(client, method)(path, follow_redirects=False)
        assert response.headers['cache-control'] == 'no-store, private'
        assert response.headers['cdn-cache-control'] == 'no-store'
        assert response.headers['vercel-cdn-cache-control'] == 'no-store'

def assert_one_time_consumption(repo):
    now = auth.utcnow()
    repo.save_oauth_transaction(state_digest=token_digest('state'), cookie_digest=token_digest('cookie'), now=now.isoformat(), expires_at=(now + timedelta(minutes=10)).isoformat())
    with repo.engine.connect() as connection:
        record = dict(connection.execute(select(dbm.oauth_transactions)).mappings().one())
        assert 'state' not in record.values() and 'cookie' not in record.values()
    def consume(_):
        return repo.consume_oauth_transaction(state_digest=token_digest('state'), cookie_digest=token_digest('cookie'), now=now.isoformat())
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(consume, range(2))) == [False, True]

def test_sqlite_competing_consumers_and_additive_upgrade(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'oauth.db'}")
    repo.initialize()
    assert_one_time_consumption(repo)
    with repo.engine.begin() as connection:
        dbm.oauth_transactions.drop(connection)
        connection.execute(update(dbm.schema_version).values(version=13))
    repo.initialize(); repo.initialize()
    assert 'oauth_transactions' in inspect(repo.engine).get_table_names()
    with repo.engine.connect() as connection:
        assert connection.execute(select(dbm.schema_version.c.version)).scalar_one() == 14
    assert_one_time_consumption(repo)
    repo.engine.dispose()

def test_access_logs_redact_auth_query_only():
    import logging
    from app.security.session import OAuthAccessLogFilter
    record = logging.LogRecord('uvicorn.access', logging.INFO, '', 0, '%s - "%s %s HTTP/%s" %d',
        ('client', 'GET', CALLBACK + '?state=private-state&code=private-code', '1.1', 400), None)
    assert OAuthAccessLogFilter().filter(record)
    assert 'private-state' not in record.getMessage() and 'private-code' not in record.getMessage()
    assert CALLBACK in record.getMessage()

@pytest.mark.parametrize('failure', ['provider_failure', 'denied'])
def test_failed_provider_flow_also_consumed(isolated_auth_db, google_settings, failure):
    from fastapi import HTTPException
    with TestClient(app) as client, patch.object(auth, '_exchange_code', AsyncMock(side_effect=HTTPException(502, 'Provider unavailable'))) as exchange:
        _, query = begin_login(client)
        params = {'state': query['state'][0], 'code': 'mock'}
        if failure == 'denied':
            params['error'] = 'access_denied'
        response = client.get(CALLBACK, params=params, follow_redirects=False)
        assert response.status_code == (400 if failure == 'denied' else 502)
        response = complete(client, query)
        assert response.status_code == 400 and response.json()['detail']['reason'] == 'transaction_unavailable'
        assert exchange.await_count == (0 if failure == 'denied' else 1)
