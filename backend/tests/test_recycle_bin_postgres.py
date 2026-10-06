"""Live Phase 4.8 acceptance under the existing isolated non-bypass RLS fixture."""
import pytest
from sqlalchemy import delete, select, text, update

from app.security.rbac import AuthorizationError
from app.security.tenant_db_context import tenant_transaction
from app.storage import models as dbm
from app.storage.database import RecycleBinError
from app.models.schemas import TaskExecutionMode, TaskStatus
from test_postgres_data_plane_integration import pg_repo, seed
from test_simulation_workspace_api import completed_task


def scoped(task, user="USR-a"):
    return dict(workspace_id=task.workspace_id, user_id=user)


def evidence(repo, task):
    with tenant_transaction(repo.engine, **scoped(task)) as connection:
        return {table.name: [dict(row) for row in connection.execute(select(table).where(
            table.c.simulation_id == task.id)).mappings()]
            for table in (dbm.tasks, dbm.agent_executions, dbm.agent_messages,
                          dbm.activity_events, dbm.run_events, dbm.simulation_metrics, dbm.simulation_uploads)}


def test_live_recycle_restore_preserves_evidence_and_force_rls(pg_repo):
    task = seed(pg_repo, "T-bin", "USR-a")
    before = evidence(pg_repo, task)
    payload = task.model_dump(mode="json")
    pg_repo.recycle_simulation(task.id, **scoped(task))
    assert pg_repo.get_for_tenant(task.id, **scoped(task)) is None
    assert pg_repo.list_for_tenant(**scoped(task)) == []
    assert evidence(pg_repo, task) == before
    assert pg_repo.list_recycled_simulations(**scoped(task))[0]["id"] == task.id
    with pg_repo.engine.connect() as connection:
        row = connection.execute(text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                                     "WHERE oid=to_regclass('simulations')")).one()
        assert tuple(row) == (True, True)
        assert connection.execute(select(dbm.simulations)).all() == []
    pg_repo.recycle_simulation(task.id, action="restore", **scoped(task))
    assert pg_repo.get_for_tenant(task.id, **scoped(task)).model_dump(mode="json") == payload
    assert evidence(pg_repo, task) == before


@pytest.mark.parametrize("action", ["delete", "restore", "purge"])
def test_live_foreign_tenant_and_unscoped_operations_fail(pg_repo, action):
    task = seed(pg_repo, "T-foreign", "USR-b")
    a = pg_repo.get_personal_workspace("USR-a")["id"]
    with pytest.raises(RecycleBinError) as exc:
        pg_repo.recycle_simulation(task.id, workspace_id=a, user_id="USR-a", action=action, confirmed=True)
    assert exc.value.status_code == 404
    assert pg_repo.list_recycled_simulations(workspace_id=a, user_id="USR-a") == []
    with pytest.raises(AuthorizationError):
        pg_repo.recycle_simulation(task.id, workspace_id=task.workspace_id, user_id="USR-a", action=action, confirmed=True)
    with tenant_transaction(pg_repo.engine, workspace_id=a, user_id="USR-a") as connection:
        assert connection.execute(update(dbm.simulations).where(dbm.simulations.c.id == task.id)
            .values(deleted_at="2026-10-06T00:00:00+00:00")).rowcount == 0
        assert connection.execute(delete(dbm.simulations).where(dbm.simulations.c.id == task.id)).rowcount == 0
    assert pg_repo.get_for_tenant(task.id, **scoped(task, "USR-b")) is not None


def test_live_v9_additive_migration_preserves_payload_and_evidence(pg_repo):
    task = seed(pg_repo, "T-migrate", "USR-a")
    before = evidence(pg_repo, task)
    with pg_repo.engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX ix_simulations_workspace_deleted")
        for column in ("deleted_at", "deleted_by_user_id", "restored_at", "restored_by_user_id"):
            connection.exec_driver_sql(f"ALTER TABLE simulations DROP COLUMN {column}")
        connection.execute(update(dbm.schema_version).values(version=9))
    pg_repo.initialize()
    pg_repo.initialize()
    assert pg_repo.get_for_tenant(task.id, **scoped(task)).model_dump(mode="json") == task.model_dump(mode="json")
    assert evidence(pg_repo, task) == before
    with pg_repo.engine.connect() as connection:
        assert connection.execute(select(dbm.schema_version.c.version)).scalar_one() == 10


def test_live_completed_run_cannot_be_purged(pg_repo):
    task = seed(pg_repo, "T-protected", "USR-a")
    before = evidence(pg_repo, task)
    pg_repo.recycle_simulation(task.id, **scoped(task))
    with pytest.raises(RecycleBinError, match="Execution evidence"):
        pg_repo.recycle_simulation(task.id, action="purge", confirmed=True, **scoped(task))
    assert evidence(pg_repo, task) == before


def test_live_explicit_purge_cascades_only_unevidenced_run(pg_repo):
    workspace = pg_repo.get_personal_workspace("USR-a")["id"]
    task = completed_task("T-purge", workspace, "Never executed legacy input")
    task.status, task.output, task.execution_mode = TaskStatus.FAILED, None, TaskExecutionMode.SINGLE_AGENT
    task.duration_seconds = 0
    pg_repo.save_for_tenant(task, **scoped(task))
    pg_repo.recycle_simulation(task.id, **scoped(task))
    pg_repo.recycle_simulation(task.id, action="purge", confirmed=True, **scoped(task))
    assert not any(evidence(pg_repo, task).values())
    with tenant_transaction(pg_repo.engine, **scoped(task)) as connection:
        assert connection.execute(select(dbm.simulations).where(dbm.simulations.c.id == task.id)).all() == []
    assert pg_repo.list_recycled_simulations(**scoped(task)) == []


def test_live_removed_membership_blocks_list_restore_purge(pg_repo):
    organization, code = pg_repo.create_organization(creator_user_id="USR-a", name="Recycle IAM")
    pg_repo.join_organization(user_id="USR-b", join_code=code)
    pg_repo.change_organization_membership_role(workspace_id=organization["id"], target_user_id="USR-b",
        actor_user_id="USR-a", new_role="admin")
    task = completed_task("T-membership", organization["id"], "Retained evidence")
    pg_repo.save_for_tenant(task, **scoped(task))
    pg_repo.recycle_simulation(task.id, **scoped(task, "USR-b"))
    pg_repo.deactivate_organization_membership(workspace_id=organization["id"], target_user_id="USR-b", actor_user_id="USR-a")
    with pytest.raises(AuthorizationError):
        pg_repo.list_recycled_simulations(**scoped(task, "USR-b"))
    for action in ("restore", "purge"):
        with pytest.raises(AuthorizationError):
            pg_repo.recycle_simulation(task.id, action=action, confirmed=True, **scoped(task, "USR-b"))
    pg_repo.recycle_simulation(task.id, action="restore", **scoped(task))


# The existing graph fixture replaces every provider with deterministic local
# agents. These tests exercise real checkpoint persistence without paid calls.
from test_graph_runtime import runtime_world, new_task
from test_postgres_graph_acceptance import checkpoint_url


@pytest.mark.parametrize("mode", ["single", "fixed", "adaptive"])
def test_live_checkpoint_and_route_contract_survive_recycle_restore(runtime_world, checkpoint_url, mode):
    import asyncio
    from app.agents.checkpointing import postgres_checkpointer, checkpoint_config
    from app.api.routes import tasks as task_routes
    repo, _, _, _ = runtime_world
    task = new_task(mode)
    scope = dict(workspace_id=task.workspace_id, user_id="USR-test")
    repo.save_for_tenant(task, **scope)
    config = checkpoint_config(task_id=task.id, workspace_id=task.workspace_id)
    identity = dict(repository=repo, task_id=task.id, **scope)

    async def check():
        try:
            async with postgres_checkpointer(checkpoint_url, **identity) as saver:
                await task_routes._run_task_inner(task.id, task=task, user_id="USR-test", checkpointer=saver)
                saved = await saver.aget_tuple(config)
                assert saved is not None
                payload = repo.get_for_tenant(task.id, **scope).model_dump(mode="json")
                repo.recycle_simulation(task.id, **scope)
                with pytest.raises(AuthorizationError):
                    await saver.aget_tuple(config)
                with pytest.raises(AuthorizationError):
                    await saver.adelete_thread(config["configurable"]["thread_id"])
                with pytest.raises(RecycleBinError, match="Execution evidence"):
                    repo.recycle_simulation(task.id, action="purge", confirmed=True, **scope)
                repo.recycle_simulation(task.id, action="restore", **scope)
                restored = await saver.aget_tuple(config)
                assert restored.checkpoint == saved.checkpoint
                assert restored.metadata == saved.metadata
                assert restored.pending_writes == saved.pending_writes
                assert repo.get_for_tenant(task.id, **scope).model_dump(mode="json") == payload
        finally:
            if repo.get_for_tenant(task.id, **scope) is None:
                repo.recycle_simulation(task.id, action="restore", **scope)
            async with postgres_checkpointer(checkpoint_url, **identity) as saver:
                await saver.adelete_thread(config["configurable"]["thread_id"])
    asyncio.run(check())
