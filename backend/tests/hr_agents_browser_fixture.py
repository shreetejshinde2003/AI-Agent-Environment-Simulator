"""Disposable localhost hiring browser acceptance. Only a deterministic provider mock is used; never import in production.

Start from repository root: .venv/bin/python backend/tests/hr_agents_browser_fixture.py
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

fixture_directory = tempfile.TemporaryDirectory(prefix='fm-phase6-ui-')
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

# Test-only deterministic adapter: production always uses the real provider.
import asyncio, json
from app.agents.llm_client import LLMResponse
async def fixture_provider(**kwargs):
    await asyncio.sleep(1.5)
    data = json.loads(kwargs['prompt'])
    requirement = data['sources']['requirement']['content']
    if requirement['purpose'] == 'Provider failure fixture':
        raise RuntimeError('Test-only provider unavailable')
    if 'humanReviewNotes' in data['output_schema']['properties']:
        output = dict(title=requirement['title'], summary=requirement['purpose'],
            responsibilities=requirement['responsibilities'], requiredSkills=requirement['requiredSkills'],
            preferredSkills=[], experience='', qualifications='', humanReviewNotes=['Confirm experience expectations.'])
    else:
        output = dict(summary='Review the supplied source information.', findings=[dict(category='missing',
            source='requirement', field='experience', explanation='Experience expectations are not specified.')])
    return LLMResponse(text=json.dumps(output), input_tokens=20, output_tokens=30,
                       response_time_seconds=1.5, model='deterministic-browser-fixture')
llm_client.call_llm = fixture_provider
repository.initialize()
repository.save_user(user_record('USR-browser'))
repository.ensure_personal_workspace('USR-browser')
org, _ = repository.create_organization(creator_user_id='USR-browser', name='Hiring acceptance')
repository.assign_organization_human_role(workspace_id=org['id'], target_user_id='USR-browser',
    human_role='hr_recruiter', actor_user_id='USR-browser')
repository.assign_organization_human_role(workspace_id=org['id'], target_user_id='USR-browser',
    human_role='hr_reviewer', actor_user_id='USR-browser')
from app.models.schemas import HiringRequirementInput, RoleKnowledgeInput, JobDescriptionInput
identity = dict(workspace_id=org['id'], user_id='USR-browser')
requirement = repository.save_hiring('requirements', HiringRequirementInput(title='Platform engineer',
    purpose='Maintain internal services', responsibilities=['Maintain services'], required_skills=['Python']), **identity)
knowledge = repository.save_hiring('role_knowledge', RoleKnowledgeInput(title='Engineering knowledge', competencies=['Reliability']), **identity)
repository.save_hiring('requirements', requirement.content.model_copy(update={'title':'Platform engineer revision two'}),
    record_id=requirement.id, expected_revision=1, **identity)
repository.save_hiring('job_descriptions', JobDescriptionInput(title='Human authored engineer draft', summary='Build services',
    requirement={'id':requirement.id,'revision':1}, role_knowledge={'id':knowledge.id,'revision':1}), **identity)
repository.save_hiring('requirements', HiringRequirementInput(title='Failure acceptance', purpose='Provider failure fixture'), **identity)
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
