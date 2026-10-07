"""Phase 8 traversal over authoritative Phase 5–7 APIs; deterministic providers."""
from unittest.mock import AsyncMock
import pytest
from app.agents import llm_client
from app.storage.database import repository
from test_hiring import context, sources, create
from test_hr_review_storage import role
from test_hr_agents import response, DRAFT, ASSESSMENT, run

ROOT = '/api/v1/hiring'


def snapshot(client, headers=None):
    paths = ['/requirements', '/role-knowledge', '/job-descriptions', '/agents/runs', '/reviews']
    responses = [client.get(ROOT + path, headers=headers or {}) for path in paths]
    return responses


def test_complete_journey_retains_original_sources_ai_and_decisions(context, monkeypatch):
    client = context[0]
    role(context, 'hr_reviewer'); role(context, 'hr_approver')
    req, knowledge, payload = sources(client)
    jd = create(client, 'job-descriptions', payload)
    request = {'agentId':'hr_jd_draft', 'requirement':payload['requirement'], 'roleKnowledge':payload['roleKnowledge']}
    monkeypatch.setattr(llm_client, 'call_llm', AsyncMock(return_value=response(DRAFT)))
    proposal = run(client, request)
    assert client.get(ROOT+'/job-descriptions/'+jd['id']).json() == jd
    for kind, record in [('requirements',req), ('role-knowledge',knowledge)]:
        updated = client.put(ROOT+'/'+kind+'/'+record['id'], json={**record['content'], 'title':'New head', 'expectedRevision':1})
        assert updated.status_code == 200
    edited = client.put(ROOT+'/job-descriptions/'+jd['id'], json={**jd['content'],'summary':'Deliberate human revision','expectedRevision':1}).json()
    monkeypatch.setattr(llm_client, 'call_llm', AsyncMock(return_value=response(ASSESSMENT)))
    validation = run(client, {**request,'agentId':'hr_draft_validation','jobDescription':{'id':jd['id'],'revision':2}})
    submitted = client.post(ROOT+'/reviews', json={'jobDescription':{'id':jd['id'],'revision':2}, 'aiRunIds':[proposal['id'],validation['id']]}).json()
    for endpoint, version, decision in [('review',1,'recommend'), ('approval',2,'approve')]:
        result = client.post(ROOT+'/reviews/'+submitted['id']+'/'+endpoint, json={'expectedVersion':version,'decision':decision,'notes':'Authenticated human decision'})
        assert result.status_code == 200, result.text
    groups = snapshot(client)
    assert all(item.status_code == 200 for item in groups)
    approved = groups[4].json()[0]
    assert approved['jobDescription'] == edited and approved['requirement'] == req and approved['roleKnowledge'] == knowledge
    assert approved['status'] == 'approved' and not approved['stale']
    assert [event['action'] for event in approved['history']] == ['submit','recommend','approve']
    assert all(event['actorUserId'] == context[1]['id'] and event['occurredAt'] for event in approved['history'])
    assert {item['id'] for item in groups[3].json()} == {proposal['id'],validation['id']}
    assert all(item['hrExecution']['proposalOnly'] for item in groups[3].json())
    assert groups[0].json()[0]['revision'] == groups[1].json()[0]['revision'] == 2
    newer = client.put(ROOT+'/job-descriptions/'+jd['id'], json={**edited['content'],'summary':'New human revision after approval','expectedRevision':2}).json()
    assert newer['revision'] == 3
    historical = client.get(ROOT+'/reviews/'+submitted['id']).json()
    assert historical['stale'] and historical['status'] == 'approved' and historical['jobDescription']['revision'] == 2
    assert client.post(ROOT+'/reviews', json={'jobDescription':{'id':jd['id'],'revision':3},'aiRunIds':[validation['id']]}).status_code == 409
    fresh = client.post(ROOT+'/reviews', json={'jobDescription':{'id':jd['id'],'revision':3},'aiRunIds':[proposal['id']]}).json()
    assert fresh['status'] == 'pending_review' and fresh['version'] == 1


@pytest.mark.parametrize('roles,submit,recommend,approve', [
    ([],False,False,False), (['hr_recruiter'],True,False,False),
    (['hr_reviewer'],False,True,False), (['hr_approver'],False,True,True),
    (['hr_recruiter','hr_reviewer','hr_approver'],True,True,True)])
def test_workflow_reads_and_capabilities_follow_effective_hr_roles(context, roles, submit, recommend, approve):
    client, user, _, org, *_ = context
    sources(client)
    repository.deactivate_organization_human_role(workspace_id=org['id'], target_user_id=user['id'], human_role='hr_recruiter', actor_user_id=user['id'])
    for name in roles: role(context, name)
    assert all(r.status_code == (200 if roles else 403) for r in snapshot(client))
    caps = client.get(ROOT+'/reviews/capabilities').json()
    assert (caps['submit'],caps['recommend'],caps['approve']) == (submit,recommend,approve)
    assert client.get(ROOT+'/capabilities').json()['job_descriptions'] == submit


@pytest.mark.parametrize('boundary', ['foreign', 'personal', 'revoked_role', 'inactive_membership'])
def test_workflow_traversal_fails_closed(context, boundary):
    client, user, personal, org, *_ = context
    req, knowledge, payload = sources(client)
    jd = create(client, 'job-descriptions',payload)
    submitted = client.post(ROOT+'/reviews',json={'jobDescription':{'id':jd['id'],'revision':1}}).json()
    headers = {}
    if boundary == 'foreign':
        other, _ = repository.create_organization(creator_user_id=user['id'],name='Separate tenant')
        repository.assign_organization_human_role(workspace_id=other['id'], target_user_id=user['id'],human_role='hr_recruiter',actor_user_id=user['id'])
        headers = {'X-Workspace-Id':other['id']}
        assert all(r.status_code == 200 and r.json() == [] for r in snapshot(client,headers))
    elif boundary == 'personal': headers = {'X-Workspace-Id':personal['id']}
    elif boundary == 'revoked_role': repository.deactivate_organization_human_role(workspace_id=org['id'],target_user_id=user['id'],human_role='hr_recruiter',actor_user_id=user['id'])
    else:
        # Revocation by a distinct owner is covered by Phase 5; exercise all traversal reads.
        from sqlalchemy import update
        from app.storage import models as dbm
        with repository.engine.begin() as conn:
            conn.execute(update(dbm.organization_memberships).where(dbm.organization_memberships.c.workspace_id == org['id'],dbm.organization_memberships.c.user_id == user['id']).values(active=False))
    if boundary != 'foreign': assert all(r.status_code in {403,404} for r in snapshot(client,headers))
    for path in ['/requirements/'+req['id']+'/revisions','/role-knowledge/'+knowledge['id']+'/revisions','/job-descriptions/'+jd['id']+'/revisions','/reviews/'+submitted['id']]:
        assert client.get(ROOT+path,headers=headers).status_code in {403,404}

@pytest.mark.parametrize('kind,index', [('requirements',0),('role-knowledge',1)])
def test_exact_source_usage_includes_immutable_jd_history(context, kind, index):
    client=context[0]
    req,knowledge,payload=sources(client)
    jd=create(client,'job-descriptions',payload)
    source=(req,knowledge)[index]
    client.put(ROOT+'/'+kind+'/'+source['id'],json={**source['content'],'title':'New source head','expectedRevision':1})
    field='requirement' if kind=='requirements' else 'roleKnowledge'
    newer=client.put(ROOT+'/job-descriptions/'+jd['id'],json={**jd['content'],field:{'id':source['id'],'revision':2},'expectedRevision':1}).json()
    path=ROOT+'/'+kind+'/'+source['id']+'/revisions/'
    assert client.get(path+'1/job-descriptions').json()==[jd]
    assert client.get(path+'2/job-descriptions').json()==[newer]
    assert client.get(path+'99/job-descriptions').status_code==404
    other,_=repository.create_organization(creator_user_id=context[1]['id'],name='Other source tenant')
    repository.assign_organization_human_role(workspace_id=other['id'],target_user_id=context[1]['id'],human_role='hr_reviewer',actor_user_id=context[1]['id'])
    assert client.get(path+'1/job-descriptions',headers={'X-Workspace-Id':other['id']}).status_code==404
    repository.deactivate_organization_human_role(workspace_id=context[3]['id'],target_user_id=context[1]['id'],human_role='hr_recruiter',actor_user_id=context[1]['id'])
    assert client.get(path+'1/job-descriptions').status_code==403
