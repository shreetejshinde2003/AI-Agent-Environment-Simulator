"""Disposable LOCAL final demo/acceptance. Never load in production.

Combines the existing HR journey with SDK-mocked simulation/research execution.
No real Google or Groq call occurs. Start from the repository root using .venv.
"""
import asyncio
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from app.agents import llm_client
from pytest import MonkeyPatch
original_call = llm_client.call_llm
import hr_workflow_browser_fixture as fixture
from test_research import wire
from research_fixtures import completion
from app.api.routes import experiments
from app.experiments.research import catalog
from app.models.schemas import ResearchExperimentInput
from fastapi import BackgroundTasks

patches = MonkeyPatch()
wire(patches, fixture.repository)

async def sdk_completion(**kwargs):
    if 'Phase10 provider failure' in kwargs['messages'][-1]['content']:
        raise RuntimeError('Deterministic test-only provider failure')
    return await completion(**kwargs)

patches.setattr(llm_client._client.chat.completions, 'create', sdk_completion)
async def shared_provider(**kwargs):
    if kwargs['prompt'].startswith('{"action":'):
        return await fixture.fixture_provider(**kwargs)
    return await original_call(**kwargs)
patches.setattr(llm_client, 'call_llm', shared_provider)

async def seed_research():
    background = BackgroundTasks()
    await experiments.admit_research(ResearchExperimentInput(
        purpose='Deterministic local machinery acceptance; no live-provider conclusions',
        benchmark_ids=tuple(c.id for c in catalog()), repetitions=2), background,
        workspace_id=fixture.org['id'], user_id='USR-recruiter')
    await background()

if __name__ == '__main__':
    import uvicorn
    asyncio.run(seed_research())
    try:
        uvicorn.run(fixture.app, host='127.0.0.1', port=8019, log_level='warning')
    finally:
        patches.undo()
        fixture.repository.engine.dispose()
        fixture.fixture_directory.cleanup()
