"""Phase 8 composed journey under real restricted PostgreSQL FORCE RLS."""
import asyncio
from unittest.mock import AsyncMock
import pytest
from app.api.routes import hr_agents as routes
from app.agents import llm_client
from app.models.schemas import JobDescriptionInput, HRReviewSubmissionInput, HRReviewDecisionInput
from app.security.rbac import AuthorizationError
from app.storage.hiring import HiringError
from test_postgres_data_plane_integration import pg_repo
from test_hiring_postgres import setup
from test_hr_agents_postgres import admitted
from test_hr_agents import response


def test_pg_linked_journey_retains_ai_source_and_human_revision_history(pg_repo, monkeypatch):
    owner, member = setup(pg_repo)
    for role in ('hr_reviewer','hr_approver'):
        pg_repo.assign_organization_human_role(workspace_id=owner['workspace_id'], target_user_id=member['user_id'],human_role=role,actor_user_id=owner['user_id'])
    task = admitted(pg_repo,owner)
    monkeypatch.setattr(routes,'repository',pg_repo)
    monkeypatch.setattr(llm_client,'call_llm',AsyncMock(return_value=response()))
    asyncio.run(routes.run_hr(task.id,**owner))
    request = task.hr_execution.request
    jd = pg_repo.save_hiring('job_descriptions',JobDescriptionInput(title='Human JD',summary='Human reviewed source material',requirement=request.requirement,role_knowledge=request.role_knowledge),**owner)
    req = pg_repo.get_hiring('requirements',request.requirement.id,**owner)
    pg_repo.save_hiring('requirements',req.content.model_copy(update={'purpose':'New requirement head'}),record_id=req.id,expected_revision=1,**owner)
    submitted = pg_repo.submit_review(HRReviewSubmissionInput(job_description={'id':jd.id,'revision':1},ai_run_ids=[task.id]),**owner)
    pg_repo.decide_review(submitted.id,HRReviewDecisionInput(expected_version=1,decision='recommend',notes='Reviewer recommendation'),**member)
    approved = pg_repo.decide_review(submitted.id,HRReviewDecisionInput(expected_version=2,decision='approve',notes='Approver decision'),approval=True,**member)
    assert approved.requirement == req and approved.job_description == jd
    assert [event.actor_user_id for event in approved.history] == [owner['user_id'],member['user_id'],member['user_id']]
    assert pg_repo.list_hr_runs(**member)[0].hr_execution.proposal_only
    pg_repo.save_hiring('job_descriptions',jd.content.model_copy(update={'summary':'Human edited after approval'}),record_id=jd.id,expected_revision=1,**owner)
    historical = pg_repo.list_reviews(**member)[0]
    assert historical.status == 'approved' and historical.stale and historical.job_description.revision == 1
    fresh = pg_repo.submit_review(HRReviewSubmissionInput(job_description={'id':jd.id,'revision':2}),**owner)
    assert fresh.status == 'pending_review' and len(fresh.history) == 1
    other,_ = pg_repo.create_organization(creator_user_id=member['user_id'],name='Foreign HR tenant')
    foreign = dict(workspace_id=other['id'],user_id=member['user_id'])
    pg_repo.assign_organization_human_role(workspace_id=other['id'],target_user_id=member['user_id'],human_role='hr_approver',actor_user_id=member['user_id'])
    assert pg_repo.list_reviews(**foreign) == pg_repo.list_hr_runs(**foreign) == []
    with pytest.raises(HiringError): pg_repo.get_review(approved.id,**foreign)
    for role in ('hr_recruiter','hr_reviewer','hr_approver'):
        pg_repo.deactivate_organization_human_role(workspace_id=owner['workspace_id'],target_user_id=member['user_id'],human_role=role,actor_user_id=owner['user_id'])
    for read in (pg_repo.list_reviews,pg_repo.list_hr_runs):
        with pytest.raises(AuthorizationError): read(**member)

@pytest.mark.parametrize('kind,index', [('requirements',0),('role_knowledge',1)])
def test_pg_historical_source_traversal_is_revision_and_tenant_bound(pg_repo,kind,index):
    from test_hiring_postgres import records
    owner,member=setup(pg_repo)
    saved=records(pg_repo,owner)
    source=saved[index];jd=saved[2]
    pg_repo.save_hiring(kind,source.content.model_copy(update={'title':'Updated source'}),record_id=source.id,expected_revision=1,**owner)
    field='requirement' if kind=='requirements' else 'role_knowledge'
    from app.models.schemas import HRSource
    newer=pg_repo.save_hiring('job_descriptions',jd.content.model_copy(update={field:HRSource(id=source.id,revision=2)}),record_id=jd.id,expected_revision=1,**owner)
    assert pg_repo.linked_job_descriptions(kind,source.id,1,**member)==[jd]
    assert pg_repo.linked_job_descriptions(kind,source.id,2,**member)==[newer]
    other,_=pg_repo.create_organization(creator_user_id=member['user_id'],name='Foreign history')
    pg_repo.assign_organization_human_role(workspace_id=other['id'],target_user_id=member['user_id'],human_role='hr_reviewer',actor_user_id=member['user_id'])
    with pytest.raises(HiringError):pg_repo.linked_job_descriptions(kind,source.id,1,workspace_id=other['id'],user_id=member['user_id'])
