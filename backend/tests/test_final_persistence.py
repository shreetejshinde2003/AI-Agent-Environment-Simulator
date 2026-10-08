"""Consolidated retained evidence across repeated schema-13 initialization.

Real SQLite/PostgreSQL stores; the provider SDK boundary is deterministic.
"""
import asyncio

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import select

from app.api.routes import experiments
from app.models.schemas import CustomAgentConfig, ResearchExperimentInput
from app.storage import models as dbm
from app.storage.database import Repository, SCHEMA_VERSION
from test_postgres_data_plane_integration import pg_repo
from test_hr_reviews_postgres import prepare, decision
from test_tenant_repository_primitives import make_user
from test_research import wire
from app.experiments.research import comparison


@pytest.fixture
def sqlite_repo(tmp_path):
    repo = Repository('sqlite:///' + str(tmp_path / 'final.db'))
    repo.initialize()
    for uid in ('USR-a', 'USR-b'):
        repo.save_user(make_user(uid))
        repo.ensure_personal_workspace(uid)
    try:
        yield repo
    finally:
        repo.engine.dispose()


@pytest.mark.parametrize('store', ['sqlite_repo', 'pg_repo'])
def test_final_reinitialization_retains_coexisting_hr_research_recycle_and_agent_evidence(request, store, monkeypatch):
    repo = request.getfixturevalue(store)
    owner, member, submission = prepare(repo)
    repo.decide_review(submission.id, decision(1, 'recommend'), **owner)
    approved = repo.decide_review(submission.id, decision(2, 'approve'), approval=True, **owner)
    jd = approved.job_description
    newer = repo.save_hiring('job_descriptions', jd.content.model_copy(update={'summary': 'New human revision'}),
                            record_id=jd.id, expected_revision=1, **owner)
    historical = repo.get_review(submission.id, **owner)
    assert historical.status == 'approved' and historical.stale
    assert newer.revision == 2
    custom = repo.save_custom_agent(CustomAgentConfig(name='Final retained agent', purpose='Inspect text', instructions='Summarize supplied text'), **owner)
    wire(monkeypatch, repo)
    background = BackgroundTasks()
    admitted = asyncio.run(experiments.admit_research(
        ResearchExperimentInput(benchmark_ids=('B-direct',), repetitions=2), background, **owner))
    asyncio.run(background())
    runs = repo.research_tasks(experiment_id=admitted['experimentId'], **owner)
    before = [t.model_dump(mode='json') for t in runs]
    assert comparison(runs)['comparable'] and len(runs) == 6
    recycled = runs[0]
    repo.recycle_simulation(recycled.id, **owner)
    for _ in range(2):
        repo.initialize()
    assert repo.get_review(submission.id, **owner) == historical
    assert repo.get_hiring('job_descriptions', jd.id, **owner) == newer
    assert [r.revision for r in repo.get_hiring('job_descriptions', jd.id, revisions=True, **owner)] == [1, 2]
    assert repo.get_custom_agent(custom.id, **owner) == custom
    assert repo.get_for_tenant(recycled.id, **owner) is None
    repo.recycle_simulation(recycled.id, action='restore', **owner)
    after = repo.research_tasks(experiment_id=admitted['experimentId'], **owner)
    assert [t.model_dump(mode='json') for t in after] == before
    assert comparison(after)['comparable']
    with repo.engine.connect() as connection:
        assert connection.execute(select(dbm.schema_version.c.version)).scalar_one() == SCHEMA_VERSION == 14
