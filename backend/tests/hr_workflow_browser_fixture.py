"""Disposable Phase 8 localhost browser fixture. Never load in production.
Real authenticated APIs/storage; only provider output and delayed reads are fixtures.
"""
import sys, tempfile, asyncio, json
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.config import settings
fixture_directory=tempfile.TemporaryDirectory(prefix='fm-phase8-ui-')
settings.DATABASE_URL='sqlite:///'+str(Path(fixture_directory.name)/'ui.db')
settings.LANGGRAPH_RUNTIME_ENABLED=False
settings.CHECKPOINT_DATABASE_URL=''
settings.GROQ_API_KEY=settings.OPENAI_API_KEY=settings.ANTHROPIC_API_KEY=''
settings.CORS_ORIGINS=['http://127.0.0.1:5179']
from app.main import app
from app.storage.database import repository
from app.models.schemas import HiringRequirementInput, RoleKnowledgeInput
from app.security.session import create_opaque_token, token_digest, session_expiry
from app.agents import llm_client
from app.agents.llm_client import LLMResponse
from test_simulation_workspace_api import user_record
from fastapi.responses import RedirectResponse

async def fixture_provider(**kwargs):
    await asyncio.sleep(0.3)
    data=json.loads(kwargs['prompt'])
    requirement=data['sources']['requirement']['content']
    if requirement['purpose']=='Provider failure fixture': raise RuntimeError('Test-only failure')
    output=dict(title=requirement['title'],summary=requirement['purpose'],responsibilities=requirement['responsibilities'],requiredSkills=requirement['requiredSkills'],preferredSkills=[],experience='',qualifications='',humanReviewNotes=['Human confirmation required.']) if 'humanReviewNotes' in data['output_schema']['properties'] else dict(summary='Inspect saved source material.',findings=[dict(category='missing',source='requirement',field='experience',explanation='Confirm experience expectations.')])
    return LLMResponse(text=json.dumps(output),input_tokens=20,output_tokens=30,response_time_seconds=0.3,model='deterministic-browser-fixture')
llm_client.call_llm=fixture_provider
repository.initialize()
users=('recruiter','reviewer','approver','combined','iamadmin','member')
for user in users:
    repository.save_user(user_record('USR-'+user));repository.ensure_personal_workspace('USR-'+user)
org,code=repository.create_organization(creator_user_id='USR-recruiter',name='Phase 8 hiring acceptance')
for user in users[1:]: repository.join_organization(user_id='USR-'+user,join_code=code)
repository.change_organization_membership_role(workspace_id=org['id'],target_user_id='USR-iamadmin',actor_user_id='USR-recruiter',new_role='admin')
for user in users:
    roles=('hr_recruiter','hr_reviewer','hr_approver') if user=='combined' else ('hr_'+user,) if user in users[:3] else ()
    for role in roles:repository.assign_organization_human_role(workspace_id=org['id'],target_user_id='USR-'+user,human_role=role,actor_user_id='USR-recruiter')
    repository.create_organization(creator_user_id='USR-'+user,name='IAM only — '+user)
identity=dict(workspace_id=org['id'],user_id='USR-recruiter')
req=repository.save_hiring('requirements',HiringRequirementInput(title='Platform engineer',purpose='Build reliable internal services',required_skills=['Python']),**identity)
repository.save_hiring('requirements',req.content.model_copy(update={'purpose':'Expanded service ownership','status':'active'}),record_id=req.id,expected_revision=1,**identity)
knowledge=repository.save_hiring('role_knowledge',RoleKnowledgeInput(title='Engineering knowledge',competencies=['Reliability']),**identity)
repository.save_hiring('role_knowledge',knowledge.content.model_copy(update={'competencies':['Reliability','Ownership']}),record_id=knowledge.id,expected_revision=1,**identity)
repository.save_hiring('requirements',HiringRequirementInput(title='Provider failure acceptance',purpose='Provider failure fixture'),**identity)
tokens={}
for user in users:
    tokens[user]=create_opaque_token();repository.save_auth_session(dict(id='S-'+user,user_id='USR-'+user,token_digest=token_digest(tokens[user]),created_at=datetime.now(timezone.utc).isoformat(),expires_at=session_expiry().isoformat(),revoked_at=None))
@app.get('/_local_browser_fixture/{user}')
async def fixture_session(user:str):
    response=RedirectResponse('http://127.0.0.1:5179')
    response.set_cookie('app_session',tokens[user],httponly=True,samesite='lax')
    return response
@app.middleware('http')
async def delayed_revision_reads(request,call_next):
    # A real old-workspace response arrives after navigation for stale-response acceptance.
    if request.url.path.endswith('/revisions'): await asyncio.sleep(1.2)
    return await call_next(request)
if __name__=='__main__':
    import uvicorn
    try:uvicorn.run(app,host='127.0.0.1',port=8019,log_level='warning')
    finally:repository.engine.dispose();fixture_directory.cleanup()
