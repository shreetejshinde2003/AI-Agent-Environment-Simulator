"""Tenant-scoped agent definitions and append-only, optimistic revisions."""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError

from app.core.config import settings
from app.models.schemas import CustomAgentConfig, CustomAgentDefinition
from app.security.rbac import Permission
from app.security.tenant_db_context import tenant_transaction
from app.storage import models as dbm


class AgentBuilderError(ValueError):
    def __init__(self, status, code, message):
        self.status_code = status
        self.detail = {"code": code, "message": message}
        super().__init__(message)


def config_digest(config, resolved_model):
    body = json.dumps({"config": config.model_dump(mode="json"), "resolvedModel": resolved_model},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()


class CustomAgentRepository:
    def _agent_scope(self, connection, workspace_id, user_id, permission):
        self._recycle_authorization(connection, workspace_id=workspace_id,
                                    user_id=user_id, permission=permission)

    @staticmethod
    def _agent_record(connection, agent_id, workspace_id, revision=None):
        agent = connection.execute(select(dbm.custom_agents).where(
            dbm.custom_agents.c.id == agent_id,
            dbm.custom_agents.c.workspace_id == workspace_id)).mappings().first()
        if agent is None:
            raise AgentBuilderError(404, "agent_unavailable", "Agent is unavailable.")
        row = connection.execute(select(dbm.custom_agent_revisions).where(
            dbm.custom_agent_revisions.c.agent_id == agent_id,
            dbm.custom_agent_revisions.c.workspace_id == workspace_id,
            dbm.custom_agent_revisions.c.revision == (revision or agent["revision"]))).mappings().first()
        if row is None:
            raise AgentBuilderError(404, "revision_unavailable", "Agent revision is unavailable.")
        try:
            config = CustomAgentConfig.model_validate(row["payload"])
        except ValidationError as exc:
            raise AgentBuilderError(409, "revision_integrity", "Agent revision integrity check failed.") from exc
        if config_digest(config, row["resolved_model"]) != row["config_hash"]:
            raise AgentBuilderError(409, "revision_integrity", "Agent revision integrity check failed.")
        return CustomAgentDefinition(
            id=agent_id, workspace_id=workspace_id, revision=row["revision"], config=config,
            resolved_model=row["resolved_model"], config_hash=row["config_hash"],
            created_by_user_id=agent["created_by_user_id"], created_at=agent["created_at"],
            updated_by_user_id=row["updated_by_user_id"], updated_at=row["updated_at"])

    def list_custom_agents(self, *, workspace_id, user_id):
        with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
            self._agent_scope(connection, workspace_id, user_id, Permission.AGENT_VIEW)
            ids = connection.execute(select(dbm.custom_agents.c.id).where(
                dbm.custom_agents.c.workspace_id == workspace_id).order_by(dbm.custom_agents.c.name_key)).scalars().all()
            return [self._agent_record(connection, aid, workspace_id) for aid in ids]

    def get_custom_agent(self, agent_id, *, workspace_id, user_id, revision=None, for_execution=False):
        with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
            self._agent_scope(connection, workspace_id, user_id,
                              Permission.AGENT_RUN if for_execution else Permission.AGENT_VIEW)
            current = self._agent_record(connection, agent_id, workspace_id)
            if for_execution and not current.config.active:
                raise AgentBuilderError(409, "agent_inactive", "Agent is inactive.")
            return self._agent_record(connection, agent_id, workspace_id, revision) if revision else current

    def custom_agent_revisions(self, agent_id, *, workspace_id, user_id):
        with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
            self._agent_scope(connection, workspace_id, user_id, Permission.AGENT_VIEW)
            self._agent_record(connection, agent_id, workspace_id)
            versions = connection.execute(select(dbm.custom_agent_revisions.c.revision).where(
                dbm.custom_agent_revisions.c.agent_id == agent_id,
                dbm.custom_agent_revisions.c.workspace_id == workspace_id
            ).order_by(dbm.custom_agent_revisions.c.revision)).scalars().all()
            return [self._agent_record(connection, agent_id, workspace_id, v) for v in versions]

    def custom_agent_deletion_eligibility(self, agent_id, *, workspace_id, user_id):
        """Report real dependencies without bypassing immutable revision guards.

        Every schema-14 saved definition has a retained creation revision.
        Deletion is therefore unavailable even without execution evidence.
        This read cannot authorize a future mutation or erase history.
        """
        with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
            self._agent_scope(connection, workspace_id, user_id, Permission.AGENT_MANAGE)
            agent = self._agent_record(connection, agent_id, workspace_id)
            revision_count = connection.execute(select(func.count()).select_from(dbm.custom_agent_revisions).where(
                dbm.custom_agent_revisions.c.agent_id == agent_id,
                dbm.custom_agent_revisions.c.workspace_id == workspace_id)).scalar_one()
            # Include soft-deleted runs: hiding them does not remove dependencies.
            run_count = connection.execute(select(func.count()).select_from(
                dbm.simulations.join(dbm.tasks, dbm.tasks.c.simulation_id == dbm.simulations.c.id)).where(
                    dbm.simulations.c.workspace_id == workspace_id,
                    dbm.tasks.c.assigned_agent_id == agent_id)).scalar_one()
            return {"agentId": agent_id, "eligible": False, "revision": agent.revision,
                    "revisionCount": revision_count, "runCount": run_count,
                    "reason": "execution_evidence" if run_count else "immutable_revisions",
                    "message": "Saved runs and configuration versions must be retained. Archive this agent instead."
                    if run_count else "Saved configuration versions are retained under the current policy. Archive this agent instead."}

    def save_custom_agent(self, config, *, workspace_id, user_id, agent_id=None, expected_revision=None):
        # Revalidate even trusted internal callers; no arbitrary persisted execution settings.
        config = CustomAgentConfig.model_validate(config.model_dump(mode="json"))
        resolved_model = settings.GROQ_MODEL if config.model == "default" else settings.GROQ_FAST_MODEL
        if not resolved_model or len(resolved_model) > 160:
            raise AgentBuilderError(409, "model_unavailable", "Configured model is unavailable.")
        stamp = datetime.now(timezone.utc).isoformat()
        try:
            with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
                self._agent_scope(connection, workspace_id, user_id, Permission.AGENT_MANAGE)
                if agent_id is None:
                    agent_id = "CA-" + uuid.uuid4().hex
                    revision = 1
                    connection.execute(insert(dbm.custom_agents).values(
                        id=agent_id, workspace_id=workspace_id, name_key=config.name.casefold(),
                        revision=revision, active=config.active, created_by_user_id=user_id, created_at=stamp))
                else:
                    previous = self._agent_record(connection, agent_id, workspace_id)
                    if expected_revision != previous.revision:
                        raise AgentBuilderError(409, "revision_conflict", "Agent changed; reload before saving.")
                    revision = previous.revision + 1
                    changed = connection.execute(update(dbm.custom_agents).where(
                        dbm.custom_agents.c.id == agent_id, dbm.custom_agents.c.workspace_id == workspace_id,
                        dbm.custom_agents.c.revision == expected_revision).values(
                            name_key=config.name.casefold(), revision=revision, active=config.active)).rowcount
                    if changed != 1:
                        raise AgentBuilderError(409, "revision_conflict", "Agent changed; reload before saving.")
                connection.execute(insert(dbm.custom_agent_revisions).values(
                    agent_id=agent_id, workspace_id=workspace_id, revision=revision,
                    updated_by_user_id=user_id, updated_at=stamp, resolved_model=resolved_model,
                    config_hash=config_digest(config, resolved_model), payload=config.model_dump(mode="json")))
                return self._agent_record(connection, agent_id, workspace_id)
        except IntegrityError as exc:
            raise AgentBuilderError(409, "agent_conflict", "Agent name or revision already exists in this workspace.") from exc

    def save_custom_agent_task(self, task, *, workspace_id, user_id, expected_revision):
        """Bind a queued Task to one revision atomically with live IAM and active state."""
        with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
            self._agent_scope(connection, workspace_id, user_id, Permission.AGENT_RUN)
            agent = self._agent_record(connection, task.assigned_agent_id, workspace_id)
            if not agent.config.active:
                raise AgentBuilderError(409, "agent_inactive", "Agent is inactive.")
            if agent.revision != expected_revision:
                raise AgentBuilderError(409, "revision_conflict", "Agent changed; reload before running.")
            if task.workspace_id != workspace_id:
                raise ValueError("Task workspace does not match tenant context.")
            task.custom_agent_revision = agent.revision
            task.custom_agent_config_hash = agent.config_hash
            self._save_task(connection, task)
        return task
