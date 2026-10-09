"""Loopback-only usability acceptance; disposable SQLite and mocked providers.
Never import in production. Session/test-control routes are fixture-only.
"""
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
import product_corrections_browser_fixture as base
from app.core.config import settings
from fastapi.responses import RedirectResponse, JSONResponse
fixture=base.fixture
settings.CORS_ORIGINS[:]=['http://127.0.0.1:5181']
settings.RESEARCH_LIVE_ENABLED=False
settings.RESEARCH_JUDGE_ENABLED=False
calls={'sdk':0,'hr':0}
original_sdk=base.baseline.llm_client._client.chat.completions.create
original_hr=fixture.fixture_provider
async def sdk(**kwargs):
    calls['sdk']+=1
    return await original_sdk(**kwargs)
async def hr(**kwargs):
    calls['hr']+=1
    return await original_hr(**kwargs)
base.baseline.patches.setattr(base.baseline.llm_client._client.chat.completions,'create',sdk)
base.baseline.patches.setattr(fixture,'fixture_provider',hr)
records_unavailable=False
@fixture.app.get('/_sprint/session/{user}')
def session(user:str):
    response=RedirectResponse('http://127.0.0.1:5181')
    response.set_cookie('app_session',fixture.tokens[user],httponly=True,samesite='lax')
    return response
@fixture.app.get('/_sprint/research/{state}')
def gate(state:str):
    settings.RESEARCH_LIVE_ENABLED=state=='enabled'
    return {'fixtureOnly':True,'enabled':settings.RESEARCH_LIVE_ENABLED}
@fixture.app.get('/_sprint/records/{state}')
def availability(state:str):
    global records_unavailable
    records_unavailable=state=='unavailable'
    return {'fixtureOnly':True}
@fixture.app.get('/_sprint/stats')
def stats(): return {'mockedProviderCalls':calls,'liveProvider':False}
@fixture.app.middleware('http')
async def fixture_failure(request,call_next):
    if records_unavailable and request.url.path=='/api/v1/tasks':
        return JSONResponse(status_code=503,content={'detail':'Local fixture records temporarily unavailable'})
    return await call_next(request)
if __name__=='__main__':
    import uvicorn
    try:uvicorn.run(fixture.app,host='127.0.0.1',port=8031,log_level='warning',access_log=False)
    finally:
        base.baseline.patches.undo()
        fixture.repository.engine.dispose()
        fixture.fixture_directory.cleanup()
