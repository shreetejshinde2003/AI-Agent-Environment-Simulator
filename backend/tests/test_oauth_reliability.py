"""Local OAuth recovery and shared-profile regressions; Google is mocked."""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.api.routes import auth
from app.main import app
from app.security.session import oauth_cookie_name, token_digest
from app.storage import models as dbm
from app.storage.database import repository
from test_google_auth_api import isolated_auth_db, google_settings, begin_login
from test_oauth_portability import claims, complete, CALLBACK


@pytest.mark.parametrize("failure", ["missing_cookie", "tampered_cookie", "expired", "denied", "network", "nonce"])
def test_browser_failure_recovers_without_sensitive_redirect(isolated_auth_db, google_settings, failure):
    with TestClient(app) as client, patch.object(auth, '_exchange_code', AsyncMock(return_value={'id_token': 'mock'})) as exchange, patch.object(auth, '_verify_google_id_token') as verify:
        _, first = begin_login(client)
        _, unrelated = begin_login(client)
        state = first['state'][0]
        verify.return_value = claims(first)
        params = {'state': state, 'code': 'private-code'}
        if failure == 'missing_cookie':
            client.cookies.delete(oauth_cookie_name(state))
        elif failure == 'tampered_cookie':
            client.cookies.set(oauth_cookie_name(state), 'tampered', domain='testserver.local', path=CALLBACK)
        elif failure == 'expired':
            with repository.engine.begin() as connection:
                connection.execute(update(dbm.oauth_transactions).where(dbm.oauth_transactions.c.state_digest == token_digest(state)).values(expires_at=(auth.utcnow() - timedelta(seconds=1)).isoformat()))
        elif failure == 'denied':
            params['error'] = 'private-provider-detail'
        elif failure == 'network':
            exchange.side_effect = HTTPException(502, 'private-provider-detail')
        else:
            verify.return_value['nonce'] = 'invalid'
        response = client.get(CALLBACK, params=params, headers={'Accept': 'text/html'}, follow_redirects=False)
        assert response.status_code == 302
        assert response.headers['location'] == 'http://localhost:5173/?auth=failed'
        assert response.headers['referrer-policy'] == 'no-referrer'
        assert response.headers['cache-control'] == 'no-store, private'
        assert not client.cookies.get(oauth_cookie_name(state))
        assert client.cookies.get(oauth_cookie_name(unrelated['state'][0]))
        exchange.side_effect = None
        verify.return_value = claims(unrelated)
        assert complete(client, unrelated).status_code == 302


@pytest.mark.parametrize("path", [CALLBACK, '/api/v1/auth/google/login'])
def test_config_failure_does_not_redirect_to_untrusted_frontend(isolated_auth_db, google_settings, path):
    with TestClient(app) as client, patch.object(auth.settings, 'FRONTEND_URL', 'https://attacker.example'):
        response = client.get(path, headers={'Accept': 'text/html'}, follow_redirects=False)
        assert response.status_code == 503 and 'location' not in response.headers
        assert response.headers['content-type'].startswith('text/html')
        assert 'attacker' not in response.text


def test_reverse_callbacks_replace_shared_session_and_block_stale_tab(isolated_auth_db, google_settings):
    with TestClient(app) as client, patch.object(auth, '_exchange_code', AsyncMock(return_value={'id_token': 'mock'})), patch.object(auth, '_verify_google_id_token') as verify:
        _, a = begin_login(client)
        _, b = begin_login(client)
        verify.return_value = claims(b, 'b')
        assert complete(client, b).status_code == 302
        old_token = client.cookies.get('app_session')
        old_user = client.get('/api/v1/auth/me').json()['user']['id']
        verify.return_value = claims(a, 'a')
        assert complete(client, a).status_code == 302
        user = client.get('/api/v1/auth/me').json()['user']['id']
        assert old_user != user
        assert repository.get_auth_session_by_digest(token_digest(old_token))['revoked_at']
        headers = {'X-Expected-User-Id': old_user}
        for method, path, kwargs in [('get', '/api/v1/tasks', {}), ('get', '/api/v1/workspaces', {}), ('post', '/api/v1/tasks', {'json': {'directive': 'must not execute'}}), ('post', '/api/v1/auth/logout', {})]:
            response = getattr(client, method)(path, headers=headers, **kwargs)
            assert response.status_code == 401 and response.json()['detail']['code'] == 'session_changed'
        assert client.get('/api/v1/auth/me').json()['user']['id'] == user
        assert client.get('/api/v1/tasks', headers={'X-Expected-User-Id': user}).status_code == 200
        with repository.engine.connect() as connection:
            assert connection.execute(select(dbm.simulations)).all() == []


def test_independent_profile_session_survives_other_profile_switch(isolated_auth_db, google_settings):
    with TestClient(app) as first, TestClient(app) as second, patch.object(auth, '_exchange_code', AsyncMock(return_value={'id_token': 'mock'})), patch.object(auth, '_verify_google_id_token') as verify:
        for client, identity in [(first, 'a'), (second, 'independent'), (first, 'b'), (first, 'c')]:
            _, query = begin_login(client)
            verify.return_value = claims(query, identity)
            assert complete(client, query).status_code == 302
        assert first.get('/api/v1/auth/me').json()['user']['email'] == 'c@example.com'
        assert second.get('/api/v1/auth/me').json()['user']['email'] == 'independent@example.com'


def test_logout_does_not_destroy_pending_transaction(isolated_auth_db, google_settings):
    with TestClient(app) as client, patch.object(auth, '_exchange_code', AsyncMock(return_value={'id_token': 'mock'})), patch.object(auth, '_verify_google_id_token') as verify:
        _, initial = begin_login(client)
        verify.return_value = claims(initial)
        assert complete(client, initial).status_code == 302
        _, pending = begin_login(client)
        assert client.post('/api/v1/auth/logout').status_code == 204
        assert client.get('/api/v1/auth/me').status_code == 401
        verify.return_value = claims(pending, 'next')
        assert complete(client, pending).status_code == 302
        assert client.get('/api/v1/auth/me').json()['user']['email'] == 'next@example.com'


def test_expired_session_recovers_with_fresh_login(isolated_auth_db, google_settings):
    with TestClient(app) as client, patch.object(auth, '_exchange_code', AsyncMock(return_value={'id_token': 'mock'})), patch.object(auth, '_verify_google_id_token') as verify:
        _, query = begin_login(client)
        verify.return_value = claims(query)
        assert complete(client, query).status_code == 302
        with repository.engine.begin() as connection:
            connection.execute(update(dbm.auth_sessions).values(expires_at=(auth.utcnow() - timedelta(seconds=1)).isoformat()))
        assert client.get('/api/v1/auth/me').json()['detail']['code'] == 'session_expired'
        _, query = begin_login(client)
        verify.return_value = claims(query)
        assert complete(client, query).status_code == 302
        assert client.get('/api/v1/auth/me').status_code == 200
