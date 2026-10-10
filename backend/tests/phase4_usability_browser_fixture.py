"""Local Phase 4 fixture: synthetic SQLite, mocked providers, research gates OFF.

No fixture endpoint enables Research. Persist the existing historical synthetic
sample for real read APIs; do not admit/execute a new research experiment.
"""
import json
import os
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'backend/tests')]
os.environ.update(RESEARCH_LIVE_ENABLED='false', RESEARCH_JUDGE_ENABLED='false',
                  RESEARCH_DEMO_ENABLED='false', LANGGRAPH_RUNTIME_ENABLED='false',
                  GROQ_API_KEY='mock-only-not-a-credential', GOOGLE_CLIENT_ID='',
                  GOOGLE_CLIENT_SECRET='', CHECKPOINT_DATABASE_URL='')
original_connect = socket.socket.connect

def local_connect(sock, address):
    if sock.family in (socket.AF_INET, socket.AF_INET6):
        if address[0] not in ('127.0.0.1', '::1'):
            raise AssertionError('Phase 4 external network forbidden')
    return original_connect(sock, address)

socket.socket.connect = local_connect
import hr_workflow_browser_fixture as fixture
from app.core.config import settings
from app.agents import llm_client
from app.models.schemas import Task
from fastapi.responses import JSONResponse, RedirectResponse

settings.CORS_ORIGINS[:] = ['http://127.0.0.1:5181']
settings.RESEARCH_EVIDENCE_KIND = 'deterministic_fixture'
calls = {'sdk': 0, 'hr': 0}
original_hr = fixture.fixture_provider
original_call = llm_client.call_llm

async def sdk(**kwargs):
    calls['sdk'] += 1
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content='Saved deterministic custom-agent result.'))],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7))

async def shared_provider(**kwargs):
    if kwargs['prompt'].startswith('{"action":'):
        calls['hr'] += 1
        return await original_hr(**kwargs)
    return await original_call(**kwargs)

# hr_workflow fixture replaced call_llm before import; recover the real central
# adapter function without replacing server authorization or Research gates.
import importlib
llm_client = importlib.reload(llm_client)
original_call = llm_client.call_llm
llm_client._client.chat.completions.create = sdk
llm_client.call_llm = shared_provider

sample = json.loads((ROOT / 'docs/acceptance/phase10-fixture-report.json').read_text())
trials = [Task.model_validate(item['task']) for item in sample['runEvidence']]
for trial in trials:
    trial.workspace_id = fixture.org['id']
fixture.repository.save_research_group(trials, workspace_id=fixture.org['id'], user_id='USR-recruiter')
records_unavailable = False

@fixture.app.get('/_sprint/session/{user}')
def session(user: str):
    response = RedirectResponse('http://127.0.0.1:5181')
    response.set_cookie('app_session', fixture.tokens[user], httponly=True, samesite='lax')
    return response

@fixture.app.get('/_sprint/records/{state}')
def availability(state: str):
    global records_unavailable
    records_unavailable = state == 'unavailable'
    return {'fixtureOnly': True}

@fixture.app.get('/_sprint/stats')
def stats():
    return {'mockedProviderCalls': calls, 'liveProvider': False,
            'researchLiveEnabled': settings.RESEARCH_LIVE_ENABLED,
            'researchJudgeEnabled': settings.RESEARCH_JUDGE_ENABLED,
            'researchDemoEnabled': settings.RESEARCH_DEMO_ENABLED,
            'seededHistoricalTrials': len(trials)}

@fixture.app.middleware('http')
async def fixture_failure(request, call_next):
    if records_unavailable and request.url.path == '/api/v1/tasks':
        return JSONResponse(status_code=503, content={'detail': 'Local fixture records temporarily unavailable'})
    return await call_next(request)

if __name__ == '__main__':
    import uvicorn
    print('Phase 4 fixture: isolated SQLite; 42 historical synthetic trials; Research gates OFF', flush=True)
    try:
        uvicorn.run(fixture.app, host='127.0.0.1', port=8031, log_level='warning', access_log=False)
    finally:
        fixture.repository.engine.dispose()
        fixture.fixture_directory.cleanup()
        socket.socket.connect = original_connect
