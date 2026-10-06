"""Optional localhost browser acceptance fixture; never imported by application code.

Use only with a disposable database. Provider responses are deterministic test
fixtures; no network provider is invoked and no production credentials are read.
"""
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings
settings.DATABASE_URL = 'sqlite:///' + str(Path(tempfile.mkdtemp(prefix='fm-phase49-ui-')) / 'ui.db')
settings.LANGGRAPH_RUNTIME_ENABLED = False
settings.CHECKPOINT_DATABASE_URL = ''
settings.GROQ_API_KEY = settings.OPENAI_API_KEY = settings.ANTHROPIC_API_KEY = ''
settings.CORS_ORIGINS = ['http://127.0.0.1:5179']
from app.main import app
from app.storage.database import repository
from app.security.session import create_opaque_token, token_digest, session_expiry
from test_simulation_workspace_api import user_record
from app.agents import llm_client
from fastapi.responses import RedirectResponse

async def fixture_provider(**kwargs):
    import json
    import asyncio
    await asyncio.sleep(.2)
    supplied = json.loads(kwargs['prompt'])
    if supplied['input'] == 'FAIL_PROVIDER':
        raise RuntimeError('Private provider error gsk_test_secret')
    return llm_client.LLMResponse('Browser test provider output: ' + supplied['input'], 12, 6, .2, kwargs['model'])
llm_client.call_llm = AsyncMock(side_effect=fixture_provider)
repository.initialize()
repository.save_user(user_record('USR-browser-check'))
w = repository.ensure_personal_workspace('USR-browser-check')
org, code = repository.create_organization(creator_user_id='USR-browser-check', name='Empty organization')
repository.save_user(user_record('USR-founder'))
member_org, member_code = repository.create_organization(creator_user_id='USR-founder', name='Member workspace')
repository.join_organization(user_id='USR-browser-check', join_code=member_code)
from app.models.schemas import CustomAgentConfig
repository.save_custom_agent(CustomAgentConfig(name='Member reviewer', purpose='Review', instructions='Summarize'),
    workspace_id=member_org['id'], user_id='USR-founder')
token = create_opaque_token()
repository.save_auth_session(dict(id='S-browser-check', user_id='USR-browser-check', token_digest=token_digest(token),
    created_at=datetime.now(timezone.utc).isoformat(), expires_at=session_expiry().isoformat(), revoked_at=None))
@app.get('/_local_browser_fixture')
async def fixture_session():
    response = RedirectResponse('http://127.0.0.1:5179')
    response.set_cookie('app_session', token, httponly=True, samesite='lax')
    return response
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8019, log_level='warning')
