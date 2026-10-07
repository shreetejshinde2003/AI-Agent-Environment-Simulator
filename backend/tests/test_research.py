"""Phase 9 deterministic machinery acceptance through the real execution engine."""
import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.api.routes import experiments, tasks, simulation
from app.agents import llm_client
from app.core.config import settings
from app.experiments.research import catalog, canonical_hash, comparison, deterministic_quality, describe, report, run_metrics
from app.main import app
from app.models.schemas import ResearchExperimentInput, HumanRubricInput, BenchmarkCase, TaskStatus, RunEvent
from app.storage.database import Repository
from app.security.session import create_opaque_token, token_digest, session_expiry
from test_tenant_repository_primitives import make_user
from research_fixtures import completion


def wire(monkeypatch, repo):
    # Every writer in the existing engine must use the same disposable store.
    from app.api.routes import auth, workspaces, messages, simulations, agents, uploads, datasets
    import app.main as main
    for module in (main, experiments, tasks, simulation, auth, workspaces, messages, simulations, agents, uploads, datasets):
        monkeypatch.setattr(module, "repository", repo)
    monkeypatch.setattr(settings, "RESEARCH_LIVE_ENABLED", True)
    monkeypatch.setattr(settings, "RESEARCH_EVIDENCE_KIND", "deterministic_fixture")
    from app.experiments.provenance import sha256_text
    monkeypatch.setattr(settings, "RESEARCH_FIXTURE_SHA256", sha256_text(Path(__file__).with_name("research_fixtures.py").read_text()))
    monkeypatch.setattr(settings, "LANGGRAPH_RUNTIME_ENABLED", False)
    monkeypatch.setattr(llm_client._client.chat.completions, "create", AsyncMock(side_effect=completion))


def add_session(repo, uid):
    token = create_opaque_token()
    repo.save_auth_session(dict(id='SES-'+uid, user_id=uid, token_digest=token_digest(token), created_at=datetime.now(timezone.utc).isoformat(), expires_at=session_expiry().isoformat(), revoked_at=None))
    return token


@pytest.fixture
def local(tmp_path, monkeypatch):
    repo = Repository('sqlite:///'+str(tmp_path/'research.db'))
    repo.initialize()
    for uid in ('USR-a','USR-b'):
        repo.save_user(make_user(uid)); repo.ensure_personal_workspace(uid)
    wire(monkeypatch, repo)
    client = TestClient(app)
    client.cookies.set('app_session',add_session(repo,'USR-a'))
    yield repo, client
    client.close(); repo.engine.dispose(); tasks._TASKS.clear()


def create(client, **kwargs):
    result = client.post('/api/v1/experiments/research',json={'benchmarkIds':['B-direct'], **kwargs})
    assert result.status_code == 201, result.text
    return result.json()['experimentId']


def review_payload(run, count=0):
    return dict(expectedOutputSha256=run['outputSha256'], expectedReviewCount=count,
                correctness=4,relevance=4,completeness=4,clarity=4,groundedness=4,concision=4,sourceConsistency=4,notes='Source checked by test reviewer')


@pytest.mark.parametrize('case', catalog(), ids=lambda c:c.id)
def test_benchmarks_are_valid_versioned_safe_and_quality_discriminates(case, local):
    repo,client=local
    assert case.version == '1' and case.source and case.checks
    with pytest.raises(ValueError): case.version='2'
    eid=create(client,benchmarkIds=[case.id])
    runs=repo.research_tasks(workspace_id=repo.get_personal_workspace('USR-a')['id'],user_id='USR-a',experiment_id=eid)
    assert len(runs)==3
    assert len({t.provenance.input_fingerprint for t in runs})==1
    for task in runs:
        assert task.status == TaskStatus.COMPLETED
        assert deterministic_quality(task)['score']==1
        task.output='Incorrect unrelated text'
        assert deterministic_quality(task)['score']==0


@pytest.mark.parametrize('bad', [dict(benchmarkIds=[]),dict(benchmarkIds=['unknown']),dict(benchmarkIds=['B-direct','B-direct']),dict(modes=[]),dict(modes=['single','single']),dict(modes=['custom']),dict(repetitions=0),dict(repetitions=6),dict(repetitions=True),dict(repetitions=1.5),dict(purpose=' '),dict(benchmarkVersion='2'),dict(extra='spoof'),dict(benchmarkIds=[c.id for c in catalog()],repetitions=3)])
def test_invalid_configuration_persists_nothing(local,bad):
    repo,client=local
    response=client.post('/api/v1/experiments/research',json={'benchmarkIds':['B-direct'],**bad})
    assert response.status_code==422
    assert repo.list()==[]


def test_repeated_modes_group_persist_reproduce_and_export(local):
    repo,client=local
    eid=create(client,repetitions=3)
    summary=client.get('/api/v1/experiments/research/'+eid).json()
    assert summary['comparable'] and summary['status']=='complete'
    assert len(summary['runs'])==9
    assert len({r['taskId'] for r in summary['runs']})==9
    for cell in summary['cells']:
        assert cell['latency']['n']==3 and cell['latency']['sampleStdDev'] is not None
        assert cell['successRate']==1
        assert cell['tokens']['mean']==18*cell['agentCalls']['mean']
    adaptive=next(c for c in summary['cells'] if c['mode']=='adaptive')
    assert adaptive['routeConsistency']==1 and adaptive['agentCalls']['mean']==2
    fixed=next(c for c in summary['cells'] if c['mode']=='fixed')
    assert fixed['agentCalls']['mean']==5 and fixed['handoffs']['mean']==4
    export=client.get('/api/v1/experiments/research/'+eid+'/report')
    assert export.status_code==200 and 'attachment' in export.headers['content-disposition']
    saved=export.json()
    assert len(saved['runEvidence'])==9 and saved['researchConclusion']
    assert saved['observedEvidence']['configuration']['evidenceKind']=='deterministic_fixture'
    rerun=client.post('/api/v1/experiments/research/'+eid+'/rerun')
    assert rerun.status_code==201 and rerun.json()['parentExperimentId']==eid
    ids=repo.research_tasks(workspace_id=repo.get_personal_workspace('USR-a')['id'],user_id='USR-a',experiment_id=eid)
    assert len({t.provenance.input_fingerprint for t in ids})==1
    assert client.get('/api/v1/experiments/research').json()[0]['experimentId']==rerun.json()['experimentId']


def test_missing_and_zero_usage_and_unknown_latency(local):
    repo,client=local;eid=create(client)
    task=repo.list()[1]
    task.elapsed_seconds=None
    for s in task.stages: s.input_tokens=s.output_tokens=s.total_tokens=None
    m=run_metrics(task)
    assert m['elapsedSeconds'] is None and m['totalTokens']['value'] is None and m['totalTokens']['coverage']=='unavailable'
    task.stages[0].total_tokens=0
    assert run_metrics(task)['totalTokens']['coverage']=='partial'
    for s in task.stages: s.total_tokens=0
    assert run_metrics(task)['totalTokens']['value']==0
    assert describe([None])['n']==0 and describe([0])['mean']==0
    assert describe([2])['sampleStdDev'] is None


def test_provider_failure_records_downstream_nonexecution_and_continues(local,monkeypatch):
    repo,client=local
    async def fail_data(**kwargs):
        if 'structured' in kwargs['messages'][0]['content'].lower():
            raise TimeoutError('fixture timed out')
        return await completion(**kwargs)
    monkeypatch.setattr(llm_client._client.chat.completions,'create',AsyncMock(side_effect=fail_data))
    eid=create(client)
    summary=client.get('/api/v1/experiments/research/'+eid).json()
    failed=[r for r in summary['runs'] if r['status']=='failed']
    assert failed and all(r['error'] and r['failedStages'] for r in failed)
    assert any(r['notExecutedAgents'] for r in failed)
    assert summary['status']=='complete'
    assert any(r['status']=='completed' for r in summary['runs'])


def test_gate_and_judge_do_not_call_provider(local,monkeypatch):
    repo,client=local
    monkeypatch.setattr(settings,'RESEARCH_LIVE_ENABLED',False)
    assert client.post('/api/v1/experiments/research',json={'benchmarkIds':['B-direct']}).status_code==403
    assert llm_client._client.chat.completions.create.await_count==0
    monkeypatch.setattr(settings,'RESEARCH_LIVE_ENABLED',True)
    eid=create(client)
    count=llm_client._client.chat.completions.create.await_count
    run=client.get('/api/v1/experiments/research/'+eid).json()['runs'][0]
    assert client.post('/api/v1/tasks/'+run['taskId']+'/evaluate').status_code==403
    assert llm_client._client.chat.completions.create.await_count==count


def test_tenant_workspace_export_rerun_and_review_fail_closed(local):
    repo,client=local;eid=create(client)
    summary=client.get('/api/v1/experiments/research/'+eid).json();run=summary['runs'][0]
    client.cookies.set('app_session',add_session(repo,'USR-b'))
    assert client.get('/api/v1/experiments/research').json()==[]
    for suffix in ('','/report'):
        assert client.get('/api/v1/experiments/research/'+eid+suffix).status_code==404
    assert client.post('/api/v1/experiments/research/'+eid+'/rerun').status_code==404
    assert client.post('/api/v1/experiments/research/'+eid+'/runs/'+run['taskId']+'/human-review',json=review_payload(run)).status_code==404
    assert client.get('/api/v1/experiments/research/'+eid,headers={'X-Workspace-Id':repo.get_personal_workspace('USR-a')['id']}).status_code==404
    client.cookies.clear()
    assert client.get('/api/v1/experiments/benchmarks').status_code==401


def test_human_review_is_attributed_append_only_output_bound_and_conflict_safe(local):
    repo,client=local;eid=create(client)
    summary=client.get('/api/v1/experiments/research/'+eid).json();run=summary['runs'][0]
    path='/api/v1/experiments/research/'+eid+'/runs/'+run['taskId']+'/human-review'
    result=client.post(path,json=review_payload(run));assert result.status_code==200
    saved=next(r for r in result.json()['runs'] if r['taskId']==run['taskId'])
    assert saved['humanScore']==4 and saved['humanReview']['reviewerId']=='USR-a'
    assert client.post(path,json=review_payload(run)).status_code==409
    bad=review_payload(run,1);bad['expectedOutputSha256']='0'*64
    assert client.post(path,json=bad).status_code==409
    assert client.post(path,json=review_payload(run,1)).status_code==200
    task=repo.get(run['taskId']);task.human_reviews=()
    with pytest.raises(ValueError,match='append-only'):repo.save(task)


@pytest.mark.parametrize('field,value',[('correctness',0),('correctness',6),('correctness',True),('clarity',2.5),('notes',' '),('sourceConsistency',None)])
def test_human_rubric_validation(field,value):
    payload=review_payload({'outputSha256':'a'*64});payload[field]=value
    with pytest.raises(ValueError):HumanRubricInput.model_validate(payload)


def test_config_drift_deleted_trials_and_benchmark_mutation_are_exposed(local,monkeypatch):
    repo,client=local;eid=create(client)
    workspace=repo.get_personal_workspace('USR-a')['id'];runs=repo.research_tasks(workspace_id=workspace,user_id='USR-a',experiment_id=eid)
    original=runs[0].research
    runs[0].research=original.model_copy(update={'trial_number':2})
    with pytest.raises(ValueError,match='immutable'):repo.save(runs[0])
    assert not comparison(runs[:-1])['comparable']
    monkeypatch.setattr(experiments,'current_configuration',lambda:original.configuration.model_copy(update={'max_output_tokens':42}))
    assert client.post('/api/v1/experiments/research/'+eid+'/rerun').status_code==409


def test_atomic_group_rolls_back_and_pending_empty_score(local,monkeypatch):
    repo,client=local
    original=repo._save_task
    count=0
    def fail(connection,task):
        nonlocal count
        count+=1
        if count==2:raise ValueError('controlled persistence failure')
        return original(connection,task)
    monkeypatch.setattr(repo,'_save_task',fail)
    with pytest.raises(ValueError):create(client)
    assert repo.list()==[]


def test_pending_route_counts_retry_timeout_recovery_and_different_input(local):
    repo,client=local;eid=create(client)
    runs=repo.list();task=runs[0]
    task.status=TaskStatus.QUEUED
    assert deterministic_quality(task) is None
    task.status=TaskStatus.FAILED
    stamp=datetime.now(timezone.utc)
    task.events.extend([RunEvent(id='retry1',type='agent_started',timestamp=stamp,agent_id=task.stages[0].agent_id,text='retry'),RunEvent(id='timeout',type='simulation_failed',timestamp=stamp,text='Server restarted; timed out')])
    m=run_metrics(task)
    assert m['repeatedStageStarts']>=1 and m['timeoutObserved'] and m['recoveryObserved']
    task.provenance=task.provenance.model_copy(update={'input_fingerprint':'f'*64})
    assert not comparison(runs)['comparable']


def test_observed_model_and_corrupt_benchmark_checksums_block_comparison(local):
    repo,client=local;eid=create(client)
    runs=repo.list()
    runs[0].stages[0].model='different-provider-model'
    assert not comparison(runs)['comparable']
    runs[0].stages[0].model=dict(runs[0].research.configuration.agent_models)[runs[0].stages[0].agent_id]
    runs[0].research=runs[0].research.model_copy(update={'benchmark_sha256':'f'*64})
    assert not comparison(runs)['comparable']


def test_revoked_workspace_stops_worker_before_provider(local,monkeypatch):
    from app.security.rbac import AuthorizationError
    repo,client=local
    org,code=repo.create_organization(creator_user_id='USR-a',name='Worker scope fixture')
    repo.join_organization(user_id='USR-b',join_code=code)
    bg=BackgroundTasks()
    admitted=asyncio.run(experiments.admit_research(ResearchExperimentInput(benchmark_ids=('B-direct',),modes=('single',)),bg,workspace_id=org['id'],user_id='USR-b'))
    repo.deactivate_organization_membership(workspace_id=org['id'],actor_user_id='USR-a',target_user_id='USR-b')
    with pytest.raises(AuthorizationError):asyncio.run(bg())
    assert llm_client._client.chat.completions.create.await_count==0
    assert repo.get_for_tenant(admitted['runs'][0]['taskId'],workspace_id=org['id'],user_id='USR-a').status==TaskStatus.QUEUED
