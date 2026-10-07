"""Research metadata, atomic grouping and inherited FORCE RLS on PostgreSQL."""
import asyncio
import pytest
from fastapi import BackgroundTasks
from sqlalchemy import select, text
from app.api.routes import experiments
from app.experiments.research import comparison, report
from app.models.schemas import ResearchExperimentInput, HumanRubricInput
from app.storage import models as dbm
from app.security.tenant_db_context import tenant_transaction
from app.security.rbac import AuthorizationError
from test_postgres_data_plane_integration import pg_repo
from test_research import wire, review_payload


def admit(repo,monkeypatch,repetitions=2):
    wire(monkeypatch,repo)
    workspace=repo.get_personal_workspace('USR-a')['id']
    bg=BackgroundTasks()
    async def run():
        result=await experiments.admit_research(ResearchExperimentInput(benchmark_ids=('B-direct',),repetitions=repetitions),bg,workspace_id=workspace,user_id='USR-a')
        await bg()
        return result
    return workspace,asyncio.run(run())['experimentId']


def test_pg_research_execution_metrics_review_reload_and_rls(pg_repo,monkeypatch):
    repo=pg_repo;workspace,eid=admit(repo,monkeypatch)
    scope=dict(workspace_id=workspace,user_id='USR-a')
    runs=repo.research_tasks(**scope,experiment_id=eid)
    summary=comparison(runs)
    assert len(runs)==6 and summary['comparable'] and all(t.status.value=='completed' for t in runs)
    assert all(c['tokens']['n']==2 for c in summary['cells'])
    run=summary['runs'][0]
    task=repo.append_research_review(run['taskId'],HumanRubricInput.model_validate(review_payload(run)),**scope)
    assert task.human_reviews[0].reviewer_id=='USR-a'
    assert report(repo.research_tasks(**scope,experiment_id=eid))['runEvidence']
    assert repo.research_tasks(workspace_id=repo.get_personal_workspace('USR-b')['id'],user_id='USR-b',experiment_id=eid)==[]
    with pytest.raises(AuthorizationError):repo.research_tasks(workspace_id=workspace,user_id='USR-b')
    with repo.engine.connect() as connection:
        assert connection.execute(select(dbm.simulations.c.payload)).all()==[]
        assert tuple(connection.execute(text("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=to_regclass('simulations')")).one())==(True,True)
    with tenant_transaction(repo.engine,workspace_id=repo.get_personal_workspace('USR-b')['id'],user_id='USR-b') as connection:
        assert connection.execute(select(dbm.simulations.c.payload)).all()==[]


def test_pg_research_immutable_metadata_and_atomic_admission(pg_repo,monkeypatch):
    repo=pg_repo;workspace,eid=admit(repo,monkeypatch,1)
    scope=dict(workspace_id=workspace,user_id='USR-a')
    run=repo.research_tasks(**scope)[0]
    run.research=run.research.model_copy(update={'benchmark_sha256':'a'*64})
    with pytest.raises(ValueError,match='immutable'):repo.save_for_tenant(run,**scope)
    original=repo._save_task;counter=0
    def fail(connection,task):
        nonlocal counter
        counter+=1
        if counter==2:raise ValueError('fixture failure')
        original(connection,task)
    monkeypatch.setattr(repo,'_save_task',fail)
    with pytest.raises(ValueError):admit(repo,monkeypatch,1)
    assert {t.experiment_id for t in repo.research_tasks(**scope)}=={eid}


def test_pg_research_review_reauthorization_after_revocation(pg_repo,monkeypatch):
    repo=pg_repo;wire(monkeypatch,repo)
    org,code=repo.create_organization(creator_user_id='USR-a',name='Research fixture')
    repo.join_organization(user_id='USR-b',join_code=code)
    scope=dict(workspace_id=org['id'],user_id='USR-a');bg=BackgroundTasks()
    async def run():
        created=await experiments.admit_research(ResearchExperimentInput(benchmark_ids=('B-direct',)),bg,**scope)
        await bg();return created['experimentId']
    eid=asyncio.run(run())
    run=comparison(repo.research_tasks(**scope))['runs'][0]
    repo.deactivate_organization_membership(workspace_id=org['id'],actor_user_id='USR-a',target_user_id='USR-b')
    with pytest.raises(AuthorizationError):repo.append_research_review(run['taskId'],HumanRubricInput.model_validate(review_payload(run)),workspace_id=org['id'],user_id='USR-b')
    assert all(not t.human_reviews for t in repo.research_tasks(**scope,experiment_id=eid))
