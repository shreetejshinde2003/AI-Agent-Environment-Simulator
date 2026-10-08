"""Disposable real API/browser fixture. All provider calls are deterministic mocks."""
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import phase10_browser_fixture as baseline
from test_simulation_workspace_api import completed_task

original = baseline.sdk_completion
async def completion(**kwargs):
    prompt = kwargs['messages'][-1]['content']
    if 'Structured stage contract (data):\n' not in prompt:
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Saved deterministic custom-agent result.'))],
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7))
    return await original(**kwargs)
baseline.patches.setattr(baseline.llm_client._client.chat.completions, 'create', completion)
fixture = baseline.fixture
run = completed_task('T-product-purge', fixture.org['id'], 'Completed evidence for owner purge acceptance')
fixture.repository.save_for_tenant(run, workspace_id=fixture.org['id'], user_id='USR-recruiter')
# Explicit real HTTP failure for readiness acceptance; never page-state injection.
from fastapi.responses import JSONResponse, RedirectResponse
workspace_unavailable = False

@fixture.app.get('/_local_product_workspace/{state}')
async def workspace_failure(state: str):
    global workspace_unavailable
    workspace_unavailable = state == 'unavailable'
    return RedirectResponse('http://127.0.0.1:5179')

@fixture.app.middleware('http')
async def workspace_status_fixture(request, call_next):
    if workspace_unavailable and request.url.path == '/api/v1/workspaces':
        return JSONResponse(status_code=503, content={'detail': 'Workspace temporarily unavailable in local acceptance.'})
    return await call_next(request)

if __name__ == '__main__':
    import uvicorn
    try: uvicorn.run(fixture.app, host='127.0.0.1', port=8019, log_level='warning')
    finally:
        baseline.patches.undo()
        fixture.repository.engine.dispose()
        fixture.fixture_directory.cleanup()
