"""Authenticated HITL endpoints and adversarial human authority boundaries."""
import pytest
from app.storage.database import repository
from test_hiring import context, create, sources
from test_hr_review_storage import draft, role

PATH = '/api/v1/hiring/reviews'


def submission(ctx):
    jd = draft(ctx)
    response = ctx[0].post(PATH, json={'jobDescription': {'id': jd['id'], 'revision': jd['revision']}})
    assert response.status_code == 201, response.text
    return response.json()


def action(client, record, decision='recommend', approval=False, **changes):
    return client.post(PATH+'/'+record['id']+('/approval' if approval else '/review'),
        json={'expectedVersion': record['version'], 'decision': decision, 'notes': 'Human review notes', **changes})


def test_real_actor_attribution_history_and_duplicate_prevention(context):
    role(context, 'hr_reviewer'); role(context, 'hr_approver')
    record = submission(context)
    assert context[0].get(PATH).json()[0] == record
    assert context[0].get(PATH+'/'+record['id']).json() == record
    reviewed = action(context[0], record).json()
    approved = action(context[0], reviewed, 'approve', True)
    assert approved.status_code == 200
    assert approved.json()['status'] == 'approved'
    assert action(context[0], reviewed, 'approve', True).status_code == 409
    history = context[0].get(PATH+'/'+record['id']+'/history').json()
    assert len(history) == 3 and all(e['actorUserId'] == context[1]['id'] for e in history)
    assert history[-1]['notes'] == 'Human review notes'
    assert context[0].get('/api/v1/hiring/job-descriptions').json()[0]['revision'] == 1


@pytest.mark.parametrize('human_role,can_submit,can_review,can_approve,can_changes,can_reject', [
    (None, False, False, False, False, False),
    ('hr_recruiter', True, False, False, False, False),
    ('hr_reviewer', False, True, False, True, False),
    ('hr_approver', False, True, True, False, True),
])
def test_role_policy_no_iam_owner_promotion(context, human_role, can_submit, can_review, can_approve, can_changes, can_reject):
    record = submission(context)
    repository.deactivate_organization_human_role(workspace_id=context[3]['id'], target_user_id=context[1]['id'],
        human_role='hr_recruiter', actor_user_id=context[1]['id'])
    if human_role: role(context, human_role)
    capabilities = context[0].get(PATH+'/capabilities').json()
    assert capabilities == dict(submit=can_submit, recommend=can_review, approve=can_approve,
        request_changes=can_changes, reject=can_reject)
    assert action(context[0], record).status_code == (200 if can_review else 403)
    current = context[0].get(PATH+'/'+record['id'])
    if can_review:
        assert action(context[0], current.json(), 'approve', True).status_code == (200 if can_approve else 403)
    else:
        assert action(context[0], record, 'approve', True).status_code == (409 if can_approve else 403)
    assert context[0].get(PATH).status_code == (200 if human_role else 403)


@pytest.mark.parametrize('extra', [{'actorUserId': 'ai-agent'}, {'approverId':'foreign'}, {'workspaceId':'other'}, {'status':'approved'}])
def test_client_cannot_claim_actor_or_authority(context, extra):
    role(context, 'hr_approver')
    record = submission(context)
    assert action(context[0], record, **extra).status_code == 422
    assert context[0].post(PATH, json={'jobDescription': {'id': record['jobDescription']['id'], 'revision': 1}, **extra}).status_code == 422


@pytest.mark.parametrize('changes', [{'notes': ''}, {'notes':'   '}, {'notes':'x'*4001}, {'expectedVersion':True}, {'expectedVersion':0}, {'decision':'publish'}, {'decision':'ai_approved'}])
def test_decision_validation(context, changes):
    role(context, 'hr_reviewer')
    record = submission(context)
    assert action(context[0], record, **changes).status_code == 422
    assert context[0].get(PATH+'/'+record['id']).json()['version'] == 1


def test_session_personal_and_cross_tenant_error_contracts(context):
    record = submission(context); client = context[0]
    assert client.get(PATH, headers={'X-Workspace-Id': context[2]['id']}).status_code == 403
    assert client.get(PATH, headers={'X-Workspace-Id':'foreign'}).status_code == 404
    other, _ = repository.create_organization(creator_user_id=context[1]['id'], name='Other tenant')
    repository.assign_organization_human_role(workspace_id=other['id'], target_user_id=context[1]['id'], human_role='hr_approver', actor_user_id=context[1]['id'])
    assert client.get(PATH+'/'+record['id'], headers={'X-Workspace-Id':other['id']}).status_code == 404
    assert client.post(PATH+'/'+record['id']+'/approval', headers={'X-Workspace-Id':other['id']},
        json={'expectedVersion':1,'decision':'approve','notes':'Foreign'}).status_code == 404
    client.cookies.clear()
    assert client.get(PATH).status_code == 401


def test_revoked_role_denies_decision_immediately(context):
    role(context, 'hr_reviewer'); role(context, 'hr_approver')
    record = submission(context); reviewed = action(context[0], record).json()
    repository.deactivate_organization_human_role(workspace_id=context[3]['id'], target_user_id=context[1]['id'],
        human_role='hr_approver', actor_user_id=context[1]['id'])
    assert action(context[0], reviewed, 'approve', True).status_code == 403
    assert context[0].get(PATH+'/'+record['id']).json()['version'] == 2


def test_stale_submission_not_submitted_draft_and_unknown_ai(context):
    role(context, 'hr_approver')
    jd = draft(context)
    assert context[0].post(PATH, json={'jobDescription':{'id':jd['id'],'revision':99}}).status_code == 409
    assert context[0].post(PATH+'/'+jd['id']+'/approval', json={'expectedVersion':1,'decision':'approve','notes':'Never submitted'}).status_code == 404
    assert context[0].post(PATH, json={'jobDescription':{'id':jd['id'],'revision':1},'aiRunIds':['fake-ai']}).status_code == 404


def test_changes_and_resubmit_real_endpoints(context):
    role(context, 'hr_reviewer')
    record = submission(context)
    changed = action(context[0], record, 'request_changes')
    assert changed.status_code == 200 and changed.json()['status'] == 'changes_requested'
    jd = record['jobDescription']
    response = context[0].put('/api/v1/hiring/job-descriptions/'+jd['id'], json={**jd['content'], 'summary':'Human edited after feedback','expectedRevision':1})
    assert response.status_code == 200
    newer = context[0].post(PATH, json={'jobDescription':{'id':jd['id'],'revision':2}})
    assert newer.status_code == 201 and newer.json()['status'] == 'pending_review'
    assert len(context[0].get(PATH).json()) == 2


@pytest.mark.parametrize('agent', ['hr_requirement_analysis', 'hr_jd_draft', 'hr_draft_validation'])
def test_explicit_ai_association_remains_proposal(context, monkeypatch, agent):
    from unittest.mock import AsyncMock
    from app.agents import llm_client
    from test_hr_agents import run, response, DRAFT, ASSESSMENT
    role(context, 'hr_reviewer')
    jd = draft(context)
    request = {'agentId':agent, 'requirement':jd['content']['requirement'], 'roleKnowledge':jd['content']['roleKnowledge']}
    if agent == 'hr_draft_validation': request['jobDescription'] = {'id':jd['id'],'revision':1}
    monkeypatch.setattr(llm_client, 'call_llm', AsyncMock(return_value=response(DRAFT if agent == 'hr_jd_draft' else ASSESSMENT)))
    proposal = run(context[0], request)
    submitted = context[0].post(PATH, json={'jobDescription':{'id':jd['id'],'revision':1}, 'aiRunIds':[proposal['id']]})
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()['aiRunIds'] == [proposal['id']]
    assert submitted.json()['status'] == 'pending_review' and submitted.json()['version'] == 1
    assert submitted.json()['jobDescription'] == jd
    assert action(context[0], submitted.json(), 'approve', True).status_code == 403
    retained = context[0].get('/api/v1/hiring/agents/runs/'+proposal['id']).json()
    assert retained == proposal and retained['hrExecution']['proposalOnly'] is True


def test_ai_association_rejects_wrong_revision_and_failed_proposal(context, monkeypatch):
    from unittest.mock import AsyncMock
    from app.agents import llm_client
    from test_hr_agents import run, response
    role(context, 'hr_reviewer')
    jd = draft(context)
    request = {'agentId':'hr_draft_validation', 'requirement':jd['content']['requirement'],
        'roleKnowledge':jd['content']['roleKnowledge'], 'jobDescription':{'id':jd['id'],'revision':1}}
    monkeypatch.setattr(llm_client, 'call_llm', AsyncMock(return_value=response()))
    proposal = run(context[0], request)
    context[0].put('/api/v1/hiring/job-descriptions/'+jd['id'], json={**jd['content'],'expectedRevision':1,'summary':'Human revision'})
    body = {'jobDescription':{'id':jd['id'],'revision':2},'aiRunIds':[proposal['id']]}
    assert context[0].post(PATH, json=body).status_code == 409
    assert context[0].post(PATH, json={**body,'aiRunIds':[proposal['id'],proposal['id']]}).status_code == 422
    request['jobDescription']['revision']=2
    monkeypatch.setattr(llm_client, 'call_llm', AsyncMock(side_effect=RuntimeError('test-only failure')))
    failed = run(context[0], request)
    assert context[0].post(PATH, json={**body,'aiRunIds':[failed['id']]}).status_code == 409
