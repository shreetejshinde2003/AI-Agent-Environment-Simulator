"""Loopback-only OAuth fixture. Fake Google, disposable DB, no provider calls.

Run from repository root with PYTHONPATH=backend. Never import in production.
"""
import asyncio
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.responses import HTMLResponse, RedirectResponse
from app.api.routes import auth
from app.core.config import settings
from app.main import app
from app.storage.database import repository
from app.agents import llm_client

fixture_directory = tempfile.TemporaryDirectory(prefix='fm-oauth-browser-')
repository.path = str(Path(fixture_directory.name) / 'oauth.db')
repository._engine = repository._engine_url = None
settings.GOOGLE_CLIENT_ID = 'local-fixture'
settings.GOOGLE_CLIENT_SECRET = 'local-fixture'
settings.GOOGLE_REDIRECT_URI = 'https://127.0.0.1:8443/api/v1/auth/google/callback'
settings.FRONTEND_URL = 'https://127.0.0.1:8443'
settings.CORS_ORIGINS = [settings.FRONTEND_URL]
settings.LANGGRAPH_RUNTIME_ENABLED = settings.RESEARCH_LIVE_ENABLED = False
auth.GOOGLE_AUTHORIZATION_ENDPOINT = 'http://localhost:8027/test/google'


async def forbidden_provider(**kwargs):
    raise AssertionError('No live provider is allowed in OAuth acceptance')


llm_client._client.chat.completions.create = forbidden_provider


async def exchange(*, code, code_verifier):
    if code == 'network':
        raise auth.HTTPException(502, 'Fixture provider network failure')
    if code.startswith('slow:'):
        await asyncio.sleep(0.3)
    # The fixture code binds identity and nonce locally, without real Google.
    return {'id_token': code}


def verify(token):
    identity, nonce = token.split(':', 1)
    return dict(sub=identity, email=f'{identity}@example.com', email_verified=True, name=identity, nonce=nonce)


auth._exchange_code = exchange
auth._verify_google_id_token = verify


@app.get('/test/google')
def fake_google(state: str, nonce: str):
    links = ''.join('<p><a href="' + settings.GOOGLE_REDIRECT_URI + '?' + urlencode({'state': state, 'code': identity + ':' + nonce}) + '">Sign in as ' + identity + '</a></p>' for identity in ('alpha', 'beta', 'gamma', 'slow'))
    return HTMLResponse('<!doctype html><title>Mock Google</title><h1>Mock Google — local fixture</h1>' + links, headers={'Referrer-Policy': 'no-referrer'})


@app.post('/test/expire-session')
def expire_session():
    from sqlalchemy import update
    from app.storage import models as dbm
    with repository.engine.begin() as connection:
        connection.execute(update(dbm.auth_sessions).values(expires_at='2000-01-01T00:00:00+00:00'))
    return {'fixture': True}


if __name__ == '__main__':
    import uvicorn
    try:
        uvicorn.run(app, host='127.0.0.1', port=8027, log_level='warning', access_log=False)
    finally:
        if repository._engine is not None:
            repository._engine.dispose()
        fixture_directory.cleanup()
