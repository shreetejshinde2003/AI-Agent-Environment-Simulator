"""Disposable localhost hiring browser acceptance. No provider requests allowed.

Start from repository root: .venv/bin/python backend/tests/hiring_browser_fixture.py
Frontend: VITE_API_BASE_URL=http://127.0.0.1:8019 npm run dev -- --host 127.0.0.1 --port 5179
Visit http://127.0.0.1:8019/_local_browser_fixture to establish the fixture session.
"""
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings

fixture_directory = tempfile.TemporaryDirectory(prefix='fm-phase5-ui-')
settings.DATABASE_URL = 'sqlite:///' + str(Path(fixture_directory.name) / 'ui.db')
settings.LANGGRAPH_RUNTIME_ENABLED = False
settings.CHECKPOINT_DATABASE_URL = ''
settings.GROQ_API_KEY = settings.OPENAI_API_KEY = settings.ANTHROPIC_API_KEY = ''
settings.CORS_ORIGINS = ['http://127.0.0.1:5179']
from app.main import app
from app.storage.database import repository
from app.security.session import create_opaque_token, token_digest, session_expiry
from app.agents import llm_client
from test_simulation_workspace_api import user_record
from fastapi.responses import RedirectResponse

llm_client.call_llm = AsyncMock(side_effect=AssertionError('Providers are outside Phase 5 acceptance'))
repository.initialize()
repository.save_user(user_record('USR-browser'))
repository.ensure_personal_workspace('USR-browser')
org, _ = repository.create_organization(creator_user_id='USR-browser', name='Hiring acceptance')
repository.assign_organization_human_role(workspace_id=org['id'], target_user_id='USR-browser',
    human_role='hr_recruiter', actor_user_id='USR-browser')
repository.create_organization(creator_user_id='USR-browser', name='No HR roles')
repository.save_user(user_record('USR-founder'))
other, code = repository.create_organization(creator_user_id='USR-founder', name='Reviewer organization')
repository.join_organization(user_id='USR-browser', join_code=code)
repository.assign_organization_human_role(workspace_id=other['id'], target_user_id='USR-browser',
    human_role='hr_reviewer', actor_user_id='USR-founder')
token = create_opaque_token()
repository.save_auth_session(dict(id='S-browser', user_id='USR-browser', token_digest=token_digest(token),
    created_at=datetime.now(timezone.utc).isoformat(), expires_at=session_expiry().isoformat(), revoked_at=None))

@app.get('/_local_browser_fixture')
async def fixture_session():
    response = RedirectResponse('http://127.0.0.1:5179')
    response.set_cookie('app_session', token, httponly=True, samesite='lax')
    return response

if __name__ == '__main__':
    import uvicorn
    try:
        uvicorn.run(app, host='127.0.0.1', port=8019, log_level='warning')
    finally:
        repository.engine.dispose()
        fixture_directory.cleanup()
