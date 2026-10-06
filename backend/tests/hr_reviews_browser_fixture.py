"""TEST ONLY: disposable localhost HITL browser acceptance with distinct human sessions.
No production decisions, credentials or external provider requests.
"""
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings
fixture_directory = tempfile.TemporaryDirectory(prefix='fm-phase7-ui-')
settings.DATABASE_URL = 'sqlite:///' + str(Path(fixture_directory.name) / 'ui.db')
settings.LANGGRAPH_RUNTIME_ENABLED = False
settings.CHECKPOINT_DATABASE_URL = ''
settings.GROQ_API_KEY = settings.OPENAI_API_KEY = settings.ANTHROPIC_API_KEY = ''
settings.CORS_ORIGINS = ['http://127.0.0.1:5179']
from app.main import app
from app.storage.database import repository
from app.models.schemas import HiringRequirementInput, RoleKnowledgeInput, JobDescriptionInput
from app.security.session import create_opaque_token, token_digest, session_expiry
from app.agents import llm_client
from test_simulation_workspace_api import user_record
from test_hr_agents import response, ASSESSMENT
from fastapi.responses import RedirectResponse
llm_client.call_llm = AsyncMock(return_value=response(ASSESSMENT))
repository.initialize()
for user in ('recruiter', 'reviewer', 'approver'):
    repository.save_user(user_record('USR-'+user))
    repository.ensure_personal_workspace('USR-'+user)
org, code = repository.create_organization(creator_user_id='USR-recruiter', name='Phase 7 browser acceptance')
for user in ('reviewer', 'approver'): repository.join_organization(user_id='USR-'+user, join_code=code)
for user in ('recruiter', 'reviewer', 'approver'):
    repository.assign_organization_human_role(workspace_id=org['id'], target_user_id='USR-'+user,
        human_role='hr_'+user, actor_user_id='USR-recruiter')
    repository.create_organization(creator_user_id='USR-'+user, name='No HR roles — '+user)
identity = dict(workspace_id=org['id'], user_id='USR-recruiter')
req = repository.save_hiring('requirements', HiringRequirementInput(title='Platform engineer', purpose='Build reliable internal services', required_skills=['Python']), **identity)
knowledge = repository.save_hiring('role_knowledge', RoleKnowledgeInput(title='Platform engineer', competencies=['Reliability']), **identity)
repository.save_hiring('job_descriptions', JobDescriptionInput(title='Platform engineer', summary='Maintain reliable internal services.',
    responsibilities=['Maintain services'], required_skills=['Python'], requirement={'id':req.id,'revision':1},
    role_knowledge={'id':knowledge.id,'revision':1}), **identity)
tokens = {}
for user in ('recruiter', 'reviewer', 'approver'):
    tokens[user] = create_opaque_token()
    repository.save_auth_session(dict(id='SESSION-'+user, user_id='USR-'+user, token_digest=token_digest(tokens[user]),
        created_at=datetime.now(timezone.utc).isoformat(), expires_at=session_expiry().isoformat(), revoked_at=None))
@app.get('/_local_browser_fixture/{human_role}')
async def fixture_session(human_role: str):
    response = RedirectResponse('http://127.0.0.1:5179')
    response.set_cookie('app_session', tokens[human_role], httponly=True, samesite='lax')
    return response
if __name__ == '__main__':
    import uvicorn
    try: uvicorn.run(app, host='127.0.0.1', port=8019, log_level='warning')
    finally:
        repository.engine.dispose(); fixture_directory.cleanup()
