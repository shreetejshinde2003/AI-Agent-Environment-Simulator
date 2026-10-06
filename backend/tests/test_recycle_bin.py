"""Recycle-bin integration uses disposable databases and never calls a provider."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import insert, select, update

from app.security.rbac import AuthorizationError
from app.storage import models as dbm
from app.storage.database import RecycleBinError, Repository, SCHEMA_VERSION
from app.models.schemas import TaskStatus, TaskExecutionMode
from test_phase2_storage import example_task
from test_simulation_workspace_api import authenticated_context, cleanup, completed_task, user_record


@pytest.fixture
def context():
    ctx = authenticated_context()
    try:
        yield ctx
    finally:
        cleanup(ctx)


def operation(repo, task, user, **kwargs):
    return repo.recycle_simulation(task.id, workspace_id=task.workspace_id, user_id=user, **kwargs)


def snapshot(repo, task):
    with repo.engine.connect() as connection:
        return {table.name: [dict(row) for row in connection.execute(select(table).where(
            table.c.simulation_id == task.id)).mappings()]
            for table in (dbm.tasks, dbm.agent_executions, dbm.agent_messages, dbm.activity_events,
                          dbm.run_events, dbm.simulation_metrics, dbm.simulation_uploads)}


def seeded(context, evidenced=False):
    from app.storage.database import repository
    _, user, personal, _, *_ = context
    task = (example_task(datetime.now(timezone.utc)) if evidenced else
            completed_task("T-bin", personal["id"], "Private run"))
    task.workspace_id = personal["id"]
    for upload in task.uploads:
        repository.save_upload_for_tenant(upload, workspace_id=personal["id"], user_id=user["id"])
    repository.save_for_tenant(task, workspace_id=personal["id"], user_id=user["id"])
    return repository, task, user["id"]


def test_delete_restore_preserves_contract_payload_relations_and_actor_metadata(context):
    repo, task, user = seeded(context, evidenced=True)
    evidence = snapshot(repo, task)
    payload = task.model_dump(mode="json")
    result = operation(repo, task, user)
    assert result["deletedAt"] and result["deletedByUserId"] == user
    assert result["entityType"] == "simulation"
    assert snapshot(repo, task) == evidence
    assert repo.get(task.id) is None
    assert repo.get_for_workspace(task.id, task.workspace_id) is None
    assert repo.get_for_tenant(task.id, workspace_id=task.workspace_id, user_id=user) is None
    assert not repo.list() and not repo.list_for_workspace(task.workspace_id)
    assert not repo.list_for_tenant(workspace_id=task.workspace_id, user_id=user)
    assert len(repo.list_recycled_simulations(workspace_id=task.workspace_id, user_id=user)) == 1
    with pytest.raises(ValueError, match="Deleted simulations"):
        repo.save_for_tenant(task, workspace_id=task.workspace_id, user_id=user)
    restored = operation(repo, task, user, action="restore")
    assert restored["deletedAt"] is None
    assert restored["restoredAt"] and restored["restoredByUserId"] == user
    assert restored["deletedByUserId"] == user
    assert repo.get(task.id).model_dump(mode="json") == payload
    assert snapshot(repo, task) == evidence
    assert not repo.list_recycled_simulations(workspace_id=task.workspace_id, user_id=user)
    again = operation(repo, task, user)
    assert again["restoredAt"] == restored["restoredAt"]


@pytest.mark.parametrize("path", ["/tasks/T-bin", "/simulations/T-bin", "/simulations/T-bin/events",
                                  "/simulations/T-bin/export", "/tasks/T-bin/resume"])
def test_deleted_run_is_unavailable_to_active_detail_export_and_resume(context, path):
    client = context[0]
    repo, task, user = seeded(context)
    operation(repo, task, user)
    response = client.post("/api/v1" + path) if path.endswith("resume") else client.get("/api/v1" + path)
    assert response.status_code == 404


def test_deleted_runs_excluded_from_all_active_aggregations(context):
    repo, task, user = seeded(context, evidenced=True)
    client = context[0]
    operation(repo, task, user)
    assert client.get("/api/v1/tasks").json() == []
    assert client.get("/api/v1/simulations").json() == []
    assert client.get("/api/v1/messages").json() == []
    assert client.get("/api/v1/simulation/activity").json() == []
    assert client.get("/api/v1/simulations/metrics").json()["history"] == []


@pytest.mark.parametrize("action", ["delete", "restore", "purge"])
def test_cross_workspace_item_ids_are_hidden(context, action):
    repo, task, user = seeded(context)
    with pytest.raises(RecycleBinError) as failure:
        repo.recycle_simulation(task.id, workspace_id=context[3]["id"], user_id=user,
                                action=action, confirmed=True)
    assert failure.value.status_code == 404
    assert repo.list_recycled_simulations(workspace_id=context[3]["id"], user_id=user) == []


@pytest.mark.parametrize("status", [TaskStatus.QUEUED, TaskStatus.IN_PROGRESS])
def test_live_runs_cannot_be_deleted(context, status):
    repo, task, user = seeded(context)
    task.status = status
    repo.save_for_tenant(task, workspace_id=task.workspace_id, user_id=user)
    with pytest.raises(RecycleBinError) as failure:
        operation(repo, task, user)
    assert failure.value.detail["code"] == "simulation_busy"
    assert repo.get(task.id).status == status


def test_conflicts_and_missing_items_are_deterministic(context):
    repo, task, user = seeded(context)
    for action in ("restore", "purge"):
        with pytest.raises(RecycleBinError, match="not in the recycle bin"):
            operation(repo, task, user, action=action, confirmed=True)
    operation(repo, task, user)
    with pytest.raises(RecycleBinError, match="already in"):
        operation(repo, task, user)
    with pytest.raises(RecycleBinError) as missing:
        repo.recycle_simulation("missing", workspace_id=task.workspace_id, user_id=user)
    assert missing.value.status_code == 404


@pytest.mark.parametrize("evidenced", [True, False])
def test_completed_run_permanent_delete_blocked_even_without_stage_rows(context, evidenced):
    repo, task, user = seeded(context, evidenced)
    before = snapshot(repo, task)
    operation(repo, task, user)
    with pytest.raises(RecycleBinError) as failure:
        operation(repo, task, user, action="purge", confirmed=True)
    assert failure.value.detail["code"] == "execution_evidence_retained"
    assert snapshot(repo, task) == before


def test_explicit_purge_of_never_executed_failed_legacy_run_preserves_shared_upload(context):
    repo, task, user = seeded(context)
    task.status = TaskStatus.FAILED
    task.output = None
    task.duration_seconds = 0
    task.execution_mode = TaskExecutionMode.SINGLE_AGENT
    from app.models.schemas import UploadedContext
    task.uploads = [UploadedContext(id="U-shared", filename="input.txt", format="txt", size_bytes=1,
                                   created_at=datetime.now(timezone.utc), preview="x", prepared_context="x")]
    repo.save_upload_for_tenant(task.uploads[0], workspace_id=task.workspace_id, user_id=user)
    repo.save_for_tenant(task, workspace_id=task.workspace_id, user_id=user)
    other = task.model_copy(deep=True, update={"id": "T-other", "simulation_id": "T-other"})
    repo.save_for_tenant(other, workspace_id=task.workspace_id, user_id=user)
    operation(repo, task, user)
    with pytest.raises(RecycleBinError, match="confirmation"):
        operation(repo, task, user, action="purge")
    assert operation(repo, task, user, action="purge", confirmed=True)["permanentlyDeleted"]
    assert all(not rows for rows in snapshot(repo, task).values())
    assert repo.get_upload("U-shared") is not None
    assert repo.get(other.id).uploads[0].id == "U-shared"
    with repo.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    with pytest.raises(RecycleBinError) as missing:
        operation(repo, task, user, action="restore")
    assert missing.value.status_code == 404


@pytest.mark.parametrize("evidence", ["stage", "output", "started", "event", "graph", "relational_drift"])
def test_failed_run_evidence_protection(context, evidence):
    repo, task, user = seeded(context)
    task.status, task.output, task.execution_mode = TaskStatus.FAILED, None, TaskExecutionMode.SINGLE_AGENT
    task.duration_seconds = 0
    if evidence == "stage":
        from app.models.schemas import StageExecution
        task.stages = [StageExecution(agent_id="direct", output_key="output", status="completed")]
    elif evidence == "output":
        task.output = "retained"
    elif evidence == "started":
        task.execution_started_at = datetime.now(timezone.utc)
    elif evidence == "event":
        from app.models.schemas import RunEvent
        task.events = [RunEvent(id="E-protected", type="simulation_failed", text="Evidence", timestamp=datetime.now(timezone.utc))]
    elif evidence == "graph":
        task.execution_mode = TaskExecutionMode.SINGLE
    elif evidence == "relational_drift":
        # Real relational evidence must fail closed even if the payload omits it.
        repo.save_for_tenant(task, workspace_id=task.workspace_id, user_id=user)
        with repo.engine.begin() as connection:
            connection.execute(insert(dbm.run_events).values(id="E-drift", simulation_id=task.id,
                type="simulation_failed", timestamp=datetime.now(timezone.utc).isoformat(), text="Evidence"))
    if evidence != "relational_drift":
        repo.save_for_tenant(task, workspace_id=task.workspace_id, user_id=user)
    operation(repo, task, user)
    with pytest.raises(RecycleBinError, match="Execution evidence"):
        operation(repo, task, user, action="purge", confirmed=True)


def test_api_delete_list_restore_conflict_and_confirmation_contract(context):
    repo, task, user = seeded(context)
    client = context[0]
    assert client.delete(f"/api/v1/simulations/{task.id}").status_code == 200
    assert client.get("/api/v1/recycle-bin").json()[0]["deletedByUserId"] == user
    assert client.delete(f"/api/v1/simulations/{task.id}").status_code == 409
    url = f"/api/v1/recycle-bin/simulations/{task.id}"
    assert client.request("DELETE", url, json={}).status_code == 422
    assert client.request("DELETE", url, json={"confirmPermanentDeletion": "true"}).status_code == 422
    assert client.request("DELETE", url, json={"confirmPermanentDeletion": True}).status_code == 409
    assert client.post(url + "/restore").status_code == 200
    assert client.get(f"/api/v1/tasks/{task.id}").status_code == 200


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_org_roles_and_repository_recheck(context, role):
    repo, task, user = seeded(context)
    org = context[3]
    repo.save_user(user_record("USR-actor"))
    repo.save_organization_membership(dict(workspace_id=org["id"], user_id="USR-actor",
        membership_role=role, added_by_user_id=user, active=True, joined_at=datetime.now(timezone.utc).isoformat()))
    task.workspace_id = org["id"]
    task.id, task.simulation_id = "T-org", "T-org"
    repo.save_for_tenant(task, workspace_id=org["id"], user_id=user)
    if role == "member":
        with pytest.raises(AuthorizationError):
            operation(repo, task, "USR-actor")
        with pytest.raises(AuthorizationError):
            repo.list_recycled_simulations(workspace_id=org["id"], user_id="USR-actor")
    else:
        operation(repo, task, "USR-actor")
        if role == "admin":
            with pytest.raises(AuthorizationError):
                operation(repo, task, "USR-actor", action="purge", confirmed=True)
        assert operation(repo, task, "USR-actor", action="restore")["restoredByUserId"] == "USR-actor"
    with repo.engine.begin() as connection:
        connection.execute(update(dbm.organization_memberships).where(
            dbm.organization_memberships.c.user_id == "USR-actor").values(active=False))
    with pytest.raises(AuthorizationError):
        operation(repo, task, "USR-actor")


def test_foreign_identity_cannot_select_personal_bin(context):
    repo, task, _ = seeded(context)
    repo.save_user(user_record("USR-foreign"))
    with pytest.raises(AuthorizationError):
        operation(repo, task, "USR-foreign")


def test_v9_sqlite_migration_is_additive_repeatable_and_preserves_payload(context):
    repo, task, _ = seeded(context, evidenced=True)
    before = snapshot(repo, task)
    payload = repo.get(task.id).model_dump(mode="json")
    with repo.engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX ix_simulations_workspace_deleted")
        for column in ("deleted_at", "deleted_by_user_id", "restored_at", "restored_by_user_id"):
            connection.exec_driver_sql(f"ALTER TABLE simulations DROP COLUMN {column}")
        connection.execute(update(dbm.schema_version).values(version=9))
        connection.exec_driver_sql("PRAGMA user_version=9")
    repo.initialize()
    repo.initialize()
    assert repo.get(task.id).model_dump(mode="json") == payload
    assert snapshot(repo, task) == before
    with repo.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA user_version").scalar_one() == SCHEMA_VERSION == 13
        assert connection.execute(select(dbm.schema_version.c.version)).scalar_one() == 13


def test_recycle_routes_require_authentication(context):
    client = context[0]
    client.cookies.clear()
    for method, path, body in (
        ("GET", "/recycle-bin", None), ("DELETE", "/simulations/missing", None),
        ("POST", "/recycle-bin/simulations/missing/restore", None),
        ("DELETE", "/recycle-bin/simulations/missing", {"confirmPermanentDeletion": True}),
    ):
        assert client.request(method, "/api/v1" + path, json=body).status_code == 401


@pytest.mark.parametrize("role", ["admin", "member"])
def test_api_org_permissions_and_foreign_workspace_denial(context, role):
    from app.security.session import create_opaque_token, token_digest, session_expiry
    repo, task, owner = seeded(context)
    client, _, personal, org, *_ = context
    actor = "USR-api-actor"
    repo.save_user(user_record(actor))
    repo.save_organization_membership(dict(workspace_id=org["id"], user_id=actor,
        membership_role=role, added_by_user_id=owner, active=True, joined_at=datetime.now(timezone.utc).isoformat()))
    task.id, task.simulation_id, task.workspace_id = "T-api-org", "T-api-org", org["id"]
    repo.save_for_tenant(task, workspace_id=org["id"], user_id=owner)
    token = create_opaque_token()
    repo.save_auth_session(dict(id="S-api-actor", user_id=actor, token_digest=token_digest(token),
        created_at=datetime.now(timezone.utc).isoformat(), expires_at=session_expiry().isoformat(), revoked_at=None))
    client.cookies.set("app_session", token)
    headers = {"X-Workspace-Id": org["id"]}
    expected = 200 if role == "admin" else 403
    assert client.delete(f"/api/v1/simulations/{task.id}", headers=headers).status_code == expected
    assert client.get("/api/v1/recycle-bin", headers=headers).status_code == expected
    assert client.request("DELETE", f"/api/v1/recycle-bin/simulations/{task.id}",
        headers=headers, json={"confirmPermanentDeletion": True}).status_code == 403
    assert client.get("/api/v1/recycle-bin", headers={"X-Workspace-Id": personal["id"]}).status_code == 404
    if role == "admin":
        assert client.post(f"/api/v1/recycle-bin/simulations/{task.id}/restore", headers=headers).status_code == 200
    else:
        assert client.post(f"/api/v1/recycle-bin/simulations/{task.id}/restore", headers=headers).status_code == 403


def test_deleted_graph_checkpoint_boundary_fails_closed_and_restore_keeps_identity(context):
    from app.agents.checkpointing import authorize_checkpoint
    repo, task, user = seeded(context)
    operation(repo, task, user)
    with pytest.raises(AuthorizationError):
        authorize_checkpoint(repo, task_id=task.id, workspace_id=task.workspace_id, user_id=user)
    operation(repo, task, user, action="restore")
    assert authorize_checkpoint(repo, task_id=task.id, workspace_id=task.workspace_id, user_id=user).id == task.id


@pytest.mark.parametrize("action", ["delete", "restore"])
def test_concurrent_lifecycle_change_has_one_winner_and_one_conflict(context, action):
    from concurrent.futures import ThreadPoolExecutor
    repo, task, user = seeded(context)
    if action == "restore":
        operation(repo, task, user)
    def change():
        try:
            operation(repo, task, user, action=action)
            return 200
        except RecycleBinError as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: change(), range(2)))
    assert sorted(results) == [200, 409]
    assert (repo.get(task.id) is None) == (action == "delete")


@pytest.mark.parametrize("table", ["metrics", "task"])
def test_relational_evidence_drift_blocks_purge(context, table):
    repo, task, user = seeded(context)
    task.status, task.output, task.execution_mode = TaskStatus.FAILED, None, TaskExecutionMode.SINGLE_AGENT
    task.duration_seconds = 0
    repo.save_for_tenant(task, workspace_id=task.workspace_id, user_id=user)
    with repo.engine.begin() as connection:
        if table == "metrics":
            connection.execute(update(dbm.simulation_metrics).where(
                dbm.simulation_metrics.c.simulation_id == task.id).values(total_tokens=7))
        else:
            connection.execute(update(dbm.tasks).where(dbm.tasks.c.simulation_id == task.id).values(output="Retained execution"))
    operation(repo, task, user)
    with pytest.raises(RecycleBinError, match="Execution evidence"):
        operation(repo, task, user, action="purge", confirmed=True)
