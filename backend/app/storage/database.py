"""Operational persistence with SQLite fallback and PostgreSQL support.

V1 SQLite snapshots are backed up, archived, and projected into the
current relational schema. Version 3 added local Google identities and
revocable application sessions. Version 4 added the workspace/tenancy
foundation. Version 5 added organization memberships. Version 6 adds persisted
simulation workspace ownership while preserving historical run payloads. Version 7
adds the persisted organization admin role and safe role-management primitives.
Version 8 adds organization-scoped HR-domain human role assignments.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy import create_engine, delete, event, inspect, insert, select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.schemas import Task, UploadedContext
from app.storage import models as dbm
from app.security.tenant_db_context import (
    TenantContextError, tenant_transaction, bootstrap_transaction,
    apply_tenant_session_context, invitation_transaction,
    apply_invitation_membership_context, recovery_catalog_transaction,
    STARTUP_RECOVERY_PRINCIPAL,
)
from app.security.postgres_rls import install_data_plane_rls_policies, require_rls_runtime_role
from app.security.workspaces import (
    generate_join_code,
    join_code_digest,
)

SCHEMA_VERSION = 8


def normalize_url(url: str | None) -> str:
    if not url:
        return "sqlite:///./simulator.db"
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if url.startswith(("sqlite:///", "postgresql+psycopg://")):
        return url
    raise ValueError("DATABASE_URL must be SQLite or PostgreSQL")


def timestamp(value):
    return value.isoformat() if value else None


class Repository:
    def __init__(self, url: str | None):
        self.url = normalize_url(url)
        self.path = self.url.removeprefix("sqlite:///") if self.url.startswith("sqlite:///") else None
        self._engine = None
        self._engine_url = None

    @property
    def engine(self):
        # Existing tests change repository.path to isolate SQLite state.
        url = f"sqlite:///{self.path}" if self.path is not None else self.url
        if self._engine is None or self._engine_url != url:
            if self._engine is not None:
                self._engine.dispose()
            options = {"pool_pre_ping": True}
            if url.startswith("sqlite:///"):
                options["connect_args"] = {"check_same_thread": False, "timeout": 10}
            engine = create_engine(url, **options)
            if engine.dialect.name == "sqlite":
                @event.listens_for(engine, "connect")
                def enable_foreign_keys(connection, _):
                    cursor = connection.cursor()
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.close()
            self._engine = engine
            self._engine_url = url
        return self._engine

    @staticmethod
    def _ensure_simulation_workspace_column(connection):
        """Add the nullable V6 workspace ownership column to existing databases."""

        columns = {
            column["name"]
            for column in inspect(connection).get_columns("simulations")
        }

        if "workspace_id" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE simulations ADD COLUMN workspace_id VARCHAR(80) "
                "REFERENCES workspaces(id) ON DELETE RESTRICT"
            )

        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_simulations_workspace_created "
            "ON simulations (workspace_id, created_at)"
        )

    @staticmethod
    def _ensure_admin_membership_role(connection):
        """Upgrade the membership-role constraint to owner/admin/member.

        SQLite cannot alter CHECK constraints in place, so V5/V6 databases
        rebuild only the membership table while preserving every row.
        PostgreSQL can replace the named constraint directly.
        """

        if "organization_memberships" not in inspect(connection).get_table_names():
            return

        if connection.dialect.name == "sqlite":
            connection.exec_driver_sql(
                "ALTER TABLE organization_memberships "
                "RENAME TO organization_memberships_v6_archive"
            )
            connection.exec_driver_sql(
                "DROP INDEX IF EXISTS ix_org_memberships_user_active"
            )
            connection.exec_driver_sql(
                "DROP INDEX IF EXISTS ix_org_memberships_workspace_active"
            )

            dbm.organization_memberships.create(
                connection,
                checkfirst=False,
            )

            connection.exec_driver_sql(
                "INSERT INTO organization_memberships "
                "(workspace_id, user_id, membership_role, active, joined_at, added_by_user_id) "
                "SELECT workspace_id, user_id, membership_role, active, joined_at, added_by_user_id "
                "FROM organization_memberships_v6_archive"
            )
            connection.exec_driver_sql(
                "DROP TABLE organization_memberships_v6_archive"
            )
            return

        connection.exec_driver_sql(
            "ALTER TABLE organization_memberships "
            "DROP CONSTRAINT IF EXISTS ck_organization_membership_role"
        )
        connection.exec_driver_sql(
            "ALTER TABLE organization_memberships "
            "ADD CONSTRAINT ck_organization_membership_role "
            "CHECK (membership_role IN ('owner', 'admin', 'member'))"
        )

    def initialize(self):
        engine = self.engine
        if engine.dialect.name == "sqlite":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            self._initialize_sqlite()
        else:
            with engine.begin() as connection:
                # Serialize concurrent Railway workers during startup/migration.
                connection.exec_driver_sql("SELECT pg_advisory_xact_lock(721842)")
                require_rls_runtime_role(connection)

                dbm.metadata.create_all(connection)

                versions = connection.execute(
                    select(dbm.schema_version.c.version)
                ).scalars().all()

                if not versions:
                    connection.execute(
                        insert(dbm.schema_version).values(
                            version=SCHEMA_VERSION,
                            applied_at=timestamp(datetime.now(timezone.utc)),
                        )
                    )

                elif versions in ([2], [3], [4], [5], [6], [7]):
                    # V8 remains additive. create_all above safely creates
                    # newer tables; migrations add simulation ownership and,
                    # for V5/V6 membership tables, widen the role constraint.
                    previous_version = versions[0]

                    self._ensure_simulation_workspace_column(connection)
                    if previous_version in (5, 6):
                        self._ensure_admin_membership_role(connection)

                    connection.execute(
                        update(dbm.schema_version)
                        .where(
                            dbm.schema_version.c.version
                            == previous_version
                        )
                        .values(
                            version=SCHEMA_VERSION,
                            applied_at=timestamp(
                                datetime.now(timezone.utc)
                            ),
                        )
                    )

                elif versions != [SCHEMA_VERSION]:
                    raise RuntimeError(
                        "Unsupported PostgreSQL schema version"
                    )

                install_data_plane_rls_policies(connection)

    def _initialize_sqlite(self):
        with sqlite3.connect(self.path) as raw:
            version = raw.execute("PRAGMA user_version").fetchone()[0]
            names = {row[0] for row in raw.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if version > SCHEMA_VERSION:
            raise RuntimeError("Database schema is newer than this application")
        if version < SCHEMA_VERSION and any(name.endswith("_v1_archive") for name in names):
            raise RuntimeError("Interrupted V1 migration; restore the .v1 backup before retrying")
        if version == 1:
            self._migrate_v1()
            return

        if version == 0 and "simulations" in names and "schema_version" not in names:
            raise RuntimeError(
                "Unversioned database contains simulations; manual inspection required"
            )

        with self.engine.begin() as connection:
            dbm.metadata.create_all(connection)

            versions = connection.execute(
                select(dbm.schema_version.c.version)
            ).scalars().all()

            if not versions:
                connection.execute(
                    insert(dbm.schema_version).values(
                        version=SCHEMA_VERSION,
                        applied_at=timestamp(datetime.now(timezone.utc)),
                    )
                )

            elif versions in ([2], [3], [4], [5], [6], [7]):
                previous_version = versions[0]

                self._ensure_simulation_workspace_column(connection)
                if previous_version in (5, 6):
                    self._ensure_admin_membership_role(connection)

                connection.execute(
                    update(dbm.schema_version)
                    .where(
                        dbm.schema_version.c.version
                        == previous_version
                    )
                    .values(
                        version=SCHEMA_VERSION,
                        applied_at=timestamp(
                            datetime.now(timezone.utc)
                        ),
                    )
                )

            elif versions != [SCHEMA_VERSION]:
                raise RuntimeError(
                    "Unsupported SQLite schema version"
                )

        with sqlite3.connect(self.path) as raw:
            raw.execute(
                f"PRAGMA user_version={SCHEMA_VERSION}"
            )

    def _migrate_v1(self):
        # Validate before any schema change; keep an independent SQLite backup.
        with sqlite3.connect(self.path) as raw:
            old_tasks = [Task.model_validate_json(row[0]) for row in raw.execute("SELECT payload FROM simulations")]
            old_uploads = [UploadedContext.model_validate_json(row[0]) for row in raw.execute("SELECT payload FROM uploads")]
            old_agents = [(row[0], json.loads(row[1])) for row in raw.execute("SELECT id, payload FROM agent_roster")]
            suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = Path(f"{self.path}.v1.{suffix}.db")
            with sqlite3.connect(backup) as destination:
                raw.backup(destination)
        with self.engine.begin() as connection:
            for table in ("simulations", "uploads", "agent_roster"):
                connection.exec_driver_sql(f"ALTER TABLE {table} RENAME TO {table}_v1_archive")
            dbm.metadata.create_all(connection)
            connection.execute(insert(dbm.schema_version).values(
                version=SCHEMA_VERSION, applied_at=timestamp(datetime.now(timezone.utc))))
            for upload in old_uploads:
                self._save_upload(connection, upload)
            for task in old_tasks:
                self._save_task(connection, task)
            for agent_id, payload in old_agents:
                connection.execute(insert(dbm.agent_roster).values(id=agent_id, payload=payload))
        with sqlite3.connect(self.path) as raw:
            raw.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    @staticmethod
    def _upsert(connection, table, key, values):
        exists = connection.execute(select(table.c[key]).where(table.c[key] == values[key])).first()
        if exists:
            connection.execute(update(table).where(table.c[key] == values[key]).values(**values))
        else:
            connection.execute(insert(table).values(**values))

    def _save_upload(self, connection, upload: UploadedContext):
        self._upsert(connection, dbm.uploads, "id", dict(
            id=upload.id, filename=upload.filename, format=upload.format,
            size_bytes=upload.size_bytes, created_at=timestamp(upload.created_at),
            payload=upload.model_dump(mode="json")))

    def save_upload(self, upload: UploadedContext):
        with self.engine.begin() as connection:
            self._save_upload(connection, upload)

    def get_upload(self, upload_id: str):
        with self.engine.connect() as connection:
            payload = connection.execute(select(dbm.uploads.c.payload).where(dbm.uploads.c.id == upload_id)).scalar_one_or_none()
        return UploadedContext.model_validate(payload) if payload is not None else None

    def _save_task(self, connection, task: Task):
        for upload in task.uploads:
            self._save_upload(connection, upload)
        self._upsert(connection, dbm.simulations, "id", dict(
            id=task.id, owner_id=task.owner_id, workspace_id=task.workspace_id,
            dataset_id=task.dataset_id,
            dataset_checksum=task.dataset_checksum, status=task.status.value,
            execution_mode=task.execution_mode.value, task_type=task.task_type,
            created_at=timestamp(task.created_at or task.started_at),
            started_at=timestamp(task.execution_started_at), completed_at=timestamp(task.completed_at),
            payload=task.model_dump(mode="json")))
        self._upsert(connection, dbm.tasks, "id", dict(
            id=task.id, simulation_id=task.id, directive=task.directive,
            assigned_agent_id=task.assigned_agent_id, priority=task.priority.value,
            status=task.status.value, output=task.output, error=task.error))
        for table in (dbm.agent_executions, dbm.agent_messages, dbm.activity_events,
                      dbm.run_events, dbm.simulation_uploads):
            connection.execute(delete(table).where(table.c.simulation_id == task.id))
        for position, stage in enumerate(task.stages):
            connection.execute(insert(dbm.agent_executions).values(
                simulation_id=task.id, position=position, agent_id=stage.agent_id,
                output_key=stage.output_key, status=stage.status,
                started_at=timestamp(stage.started_at), completed_at=timestamp(stage.completed_at),
                duration_seconds=stage.duration_seconds, model=stage.model,
                input_tokens=stage.input_tokens, output_tokens=stage.output_tokens,
                total_tokens=stage.total_tokens, output=stage.output, error=stage.error))
        for message in task.messages:
            connection.execute(insert(dbm.agent_messages).values(
                id=message.id, simulation_id=task.id, from_agent_id=message.from_agent_id,
                to_agent_id=message.to_agent_id, kind=message.kind.value,
                output_key=message.output_key, timestamp=timestamp(message.timestamp),
                content=message.content))
        for activity in task.activities:
            connection.execute(insert(dbm.activity_events).values(
                id=activity.id, simulation_id=task.id, agent_id=activity.agent_id,
                timestamp=timestamp(activity.timestamp), text=activity.text))
        for run_event in task.events:
            connection.execute(insert(dbm.run_events).values(
                id=run_event.id, simulation_id=task.id, type=run_event.type,
                agent_id=run_event.agent_id, timestamp=timestamp(run_event.timestamp),
                text=run_event.text))
        for upload in task.uploads:
            connection.execute(insert(dbm.simulation_uploads).values(
                simulation_id=task.id, upload_id=upload.id))
        measured = [stage.total_tokens for stage in task.stages if stage.total_tokens is not None]
        self._upsert(connection, dbm.simulation_metrics, "simulation_id", dict(
            simulation_id=task.id, elapsed_seconds=task.elapsed_seconds,
            total_tokens=sum(measured) if measured else None, measured_stages=len(measured)))

    def save(self, task: Task):
        self._require_legacy_sqlite()
        with self.engine.begin() as connection:
            self._save_task(connection, task)

    def save_for_tenant(
        self,
        task: Task,
        *,
        workspace_id: str,
        user_id: str,
    ):
        """Persist one simulation inside an explicit trusted tenant context.

        The task payload must already belong to the selected workspace.  The
        mismatch check happens before opening a transaction so caller mistakes
        cannot be hidden by PostgreSQL RLS.
        """

        if task.workspace_id != workspace_id:
            raise ValueError("Task workspace does not match tenant context.")

        with tenant_transaction(
            self.engine,
            workspace_id=workspace_id,
            user_id=user_id,
        ) as connection:
            self._save_task(connection, task)

    def get_for_tenant(
        self,
        task_id: str,
        *,
        workspace_id: str,
        user_id: str,
    ):
        """Read one simulation through a transaction carrying tenant context."""

        with tenant_transaction(
            self.engine,
            workspace_id=workspace_id,
            user_id=user_id,
        ) as connection:
            row = connection.execute(
                select(
                    dbm.simulations.c.workspace_id,
                    dbm.simulations.c.payload,
                ).where(
                    dbm.simulations.c.id == task_id,
                    dbm.simulations.c.workspace_id == workspace_id,
                )
            ).mappings().first()
        return self._task_from_row(row)

    def list_for_tenant(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ):
        """List simulations only inside the selected trusted tenant context."""

        with tenant_transaction(
            self.engine,
            workspace_id=workspace_id,
            user_id=user_id,
        ) as connection:
            rows = connection.execute(
                select(
                    dbm.simulations.c.workspace_id,
                    dbm.simulations.c.payload,
                ).where(
                    dbm.simulations.c.workspace_id == workspace_id
                ).order_by(
                    dbm.simulations.c.created_at,
                    dbm.simulations.c.id,
                )
            ).mappings().all()
        return [self._task_from_row(row) for row in rows]

    @staticmethod
    def _task_from_row(row):
        if row is None:
            return None
        task = Task.model_validate(row["payload"])
        if task.workspace_id != row["workspace_id"]:
            task = task.model_copy(
                update={"workspace_id": row["workspace_id"]}
            )
        return task

    def get(self, task_id: str):
        self._require_legacy_sqlite()
        with self.engine.connect() as connection:
            row = connection.execute(
                select(
                    dbm.simulations.c.workspace_id,
                    dbm.simulations.c.payload,
                ).where(dbm.simulations.c.id == task_id)
            ).mappings().first()
        return self._task_from_row(row)

    def get_for_workspace(self, task_id: str, workspace_id: str):
        self._require_legacy_sqlite()
        with self.engine.connect() as connection:
            row = connection.execute(
                select(
                    dbm.simulations.c.workspace_id,
                    dbm.simulations.c.payload,
                ).where(
                    dbm.simulations.c.id == task_id,
                    dbm.simulations.c.workspace_id == workspace_id,
                )
            ).mappings().first()
        return self._task_from_row(row)

    def list(self):
        self._require_legacy_sqlite()
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(
                    dbm.simulations.c.workspace_id,
                    dbm.simulations.c.payload,
                ).order_by(
                    dbm.simulations.c.created_at,
                    dbm.simulations.c.id,
                )
            ).mappings().all()
        return [self._task_from_row(row) for row in rows]

    def list_for_workspace(self, workspace_id: str):
        self._require_legacy_sqlite()
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(
                    dbm.simulations.c.workspace_id,
                    dbm.simulations.c.payload,
                ).where(
                    dbm.simulations.c.workspace_id == workspace_id
                ).order_by(
                    dbm.simulations.c.created_at,
                    dbm.simulations.c.id,
                )
            ).mappings().all()
        return [self._task_from_row(row) for row in rows]

    def _require_legacy_sqlite(self):
        """Legacy fixture/development methods cannot open unscoped PG access."""
        if self.engine.dialect.name == "postgresql":
            raise TenantContextError(
                "PostgreSQL simulation access requires trusted workspace and user context."
            )

    def recover_interrupted_tasks(self, recover: Callable[[Task], None]) -> int:
        """Startup-only maintenance; never a request-facing global run scan.

        PostgreSQL enumerates identity IDs, then a bounded creator/owner catalog
        scope (including inactive workspaces), then locks pending rows per tenant. The principal is
        explicitly system maintenance, not an impersonated human or bypass role.
        SQLite also preserves historical workspace-less local run recovery.
        """
        engine = self.engine
        pending = ("queued", "in_progress")
        count = 0

        def recover_rows(connection, workspace_id=None):
            nonlocal count
            statement = select(
                dbm.simulations.c.workspace_id, dbm.simulations.c.payload
            ).where(dbm.simulations.c.status.in_(pending))
            if workspace_id is not None:
                statement = statement.where(
                    dbm.simulations.c.workspace_id == workspace_id
                ).with_for_update()
            rows = connection.execute(statement).mappings().all()
            for row in rows:
                task = self._task_from_row(row)
                recover(task)
                self._save_task(connection, task)
                count += 1

        if engine.dialect.name == "postgresql":
            with engine.connect() as connection:
                owner_ids = connection.execute(
                    select(dbm.users.c.id).order_by(dbm.users.c.id)
                ).scalars().all()
            workspace_ids = set()
            for owner_id in owner_ids:
                with recovery_catalog_transaction(engine, owner_user_id=owner_id) as connection:
                    workspace_ids.update(connection.execute(
                        select(dbm.workspaces.c.id).where(
                            (dbm.workspaces.c.created_by_user_id == owner_id)
                            | (dbm.workspaces.c.personal_owner_user_id == owner_id)
                        )
                    ).scalars().all())
            for workspace_id in sorted(workspace_ids):
                with tenant_transaction(
                    engine, workspace_id=workspace_id,
                    user_id=STARTUP_RECOVERY_PRINCIPAL,
                ) as connection:
                    recover_rows(connection, workspace_id)
        else:
            with engine.begin() as connection:
                recover_rows(connection)
        return count

    def backfill_legacy_simulations_for_user(self, user_id: str) -> int:
        """Move legacy unowned runs to the oldest local user's Personal Workspace.

        Before authentication existed, simulation history was one shared
        workspace. The oldest local identity is therefore the deterministic
        migration owner; later accounts must never race to claim those rows.
        """

        # PostgreSQL ownership must be resolved explicitly before first RLS
        # activation. Login cannot perform a hidden global ownership write.
        if self.engine.dialect.name == "postgresql":
            return 0

        user = self.get_user(user_id)
        if user is None or not user["active"]:
            raise ValueError("Workspace user is unavailable.")

        with self.engine.connect() as connection:
            first_user_id = connection.execute(
                select(dbm.users.c.id)
                .where(dbm.users.c.active.is_(True))
                .order_by(dbm.users.c.created_at, dbm.users.c.id)
                .limit(1)
            ).scalar_one_or_none()

        if first_user_id != user_id:
            return 0

        personal = self.ensure_personal_workspace(user_id)

        with self.engine.begin() as connection:
            result = connection.execute(
                update(dbm.simulations)
                .where(dbm.simulations.c.workspace_id.is_(None))
                .values(workspace_id=personal["id"])
            )

        return int(result.rowcount or 0)

    def save_user(self, user: dict):
        """Create or update one locally persisted Google identity."""

        with self.engine.begin() as connection:
            self._upsert(
                connection,
                dbm.users,
                "id",
                user,
            )

    def get_user(self, user_id: str):
        with self.engine.connect() as connection:
            row = connection.execute(
                select(dbm.users).where(
                    dbm.users.c.id == user_id
                )
            ).mappings().first()

        return dict(row) if row else None

    def get_user_by_google_sub(self, google_sub: str):
        with self.engine.connect() as connection:
            row = connection.execute(
                select(dbm.users).where(
                    dbm.users.c.google_sub == google_sub
                )
            ).mappings().first()

        return dict(row) if row else None

    def save_workspace(self, workspace: dict):
        """SQLite fixture compatibility; PostgreSQL uses authorized workflows."""
        self._require_legacy_sqlite()

        with self.engine.begin() as connection:
            self._upsert(
                connection,
                dbm.workspaces,
                "id",
                workspace,
            )

    def get_workspace(self, workspace_id: str, *, user_id: str | None = None):
        if user_id is None:
            self._require_legacy_sqlite()
        transaction = (
            bootstrap_transaction(self.engine, user_id=user_id)
            if user_id is not None else self.engine.begin()
        )
        with transaction as connection:
            statement = select(dbm.workspaces).where(dbm.workspaces.c.id == workspace_id)
            if user_id is not None:
                own_membership = select(dbm.organization_memberships.c.user_id).where(
                    dbm.organization_memberships.c.workspace_id == dbm.workspaces.c.id,
                    dbm.organization_memberships.c.user_id == user_id,
                    dbm.organization_memberships.c.active.is_(True),
                ).exists()
                statement = statement.where(
                    dbm.workspaces.c.active.is_(True),
                    ((dbm.workspaces.c.kind == "personal")
                     & (dbm.workspaces.c.personal_owner_user_id == user_id))
                    | ((dbm.workspaces.c.kind == "organization") & own_membership),
                )
            row = connection.execute(statement).mappings().first()

        return dict(row) if row else None

    def get_personal_workspace(
        self,
        user_id: str,
    ):
        with bootstrap_transaction(self.engine, user_id=user_id) as connection:
            row = connection.execute(
                select(dbm.workspaces).where(
                    dbm.workspaces.c.kind
                    == "personal",
                    dbm.workspaces.c.personal_owner_user_id
                    == user_id,
                    dbm.workspaces.c.active.is_(True),
                )
            ).mappings().first()

        return dict(row) if row else None

    def ensure_personal_workspace(
        self,
        user_id: str,
    ):
        """Return the user's one private Personal Workspace.

        Creation is idempotent. The database UNIQUE constraint on
        personal_owner_user_id remains the final concurrency guard.
        """

        user = self.get_user(user_id)

        if user is None or not user["active"]:
            raise ValueError(
                "Personal Workspace owner is unavailable."
            )

        existing = self.get_personal_workspace(
            user_id
        )

        if existing is not None:
            return existing

        now = timestamp(
            datetime.now(timezone.utc)
        )

        workspace = {
            "id": (
                f"WS-{uuid.uuid4().hex[:20]}"
            ),
            "kind": "personal",
            "name": "Personal Workspace",
            "personal_owner_user_id": user_id,
            "created_by_user_id": user_id,
            "join_code_digest": None,
            "active": True,
            "created_at": now,
            "updated_at": now,
        }

        try:
            with bootstrap_transaction(self.engine, user_id=user_id) as connection:
                connection.execute(
                    insert(dbm.workspaces).values(
                        **workspace
                    )
                )

        except IntegrityError:
            # Another concurrent login may have created the same user's
            # workspace after our first lookup. Re-read rather than
            # creating or exposing a duplicate.
            existing = self.get_personal_workspace(
                user_id
            )

            if existing is not None:
                return existing

            raise

        created = self.get_personal_workspace(
            user_id
        )

        if created is None:
            raise RuntimeError(
                "Personal Workspace creation did not persist."
            )

        return created

    def resolve_workspace_for_user(
        self,
        user_id: str,
        workspace_id: str | None = None,
    ):
        """Resolve one workspace the user is allowed to access.

        No explicit workspace means the user's private Personal Workspace.
        Organization access requires an active membership.
        """

        user = self.get_user(user_id)

        if user is None or not user["active"]:
            raise ValueError(
                "Workspace user is unavailable."
            )

        if workspace_id is None:
            workspace = self.get_personal_workspace(
                user_id
            )

            if workspace is None:
                workspace = self.ensure_personal_workspace(
                    user_id
                )

            return workspace

        workspace = self.get_workspace(
            workspace_id, user_id=user_id,
        )

        if workspace is None or not workspace["active"]:
            raise PermissionError(
                "Workspace is unavailable."
            )

        if workspace["kind"] == "personal":
            if (
                workspace["personal_owner_user_id"]
                != user_id
            ):
                raise PermissionError(
                    "Workspace access denied."
                )

            return workspace

        if workspace["kind"] == "organization":
            membership = (
                self.get_organization_membership(
                    workspace_id,
                    user_id,
                )
            )

            if (
                membership is None
                or not membership["active"]
            ):
                raise PermissionError(
                    "Workspace access denied."
                )

            return workspace

        raise PermissionError(
            "Workspace access denied."
        )

    def create_organization(
        self,
        *,
        creator_user_id: str,
        name: str,
    ):
        """Atomically create an Organization and its owner membership.

        The plaintext join code is returned to the caller but never persisted.
        """

        creator = self.get_user(
            creator_user_id
        )

        if (
            creator is None
            or not creator["active"]
        ):
            raise ValueError(
                "Organization creator is unavailable."
            )

        normalized_name = " ".join(
            name.strip().split()
        )

        if (
            len(normalized_name) < 2
            or len(normalized_name) > 120
        ):
            raise ValueError(
                "Organization name must be between 2 and 120 characters."
            )

        now = timestamp(
            datetime.now(timezone.utc)
        )

        # A digest collision is extraordinarily unlikely, but retrying keeps
        # the uniqueness contract explicit and deterministic.
        for _ in range(5):
            join_code = generate_join_code()
            digest = join_code_digest(
                join_code
            )

            workspace = {
                "id": (
                    f"WS-{uuid.uuid4().hex[:20]}"
                ),
                "kind": "organization",
                "name": normalized_name,
                "personal_owner_user_id": None,
                "created_by_user_id": creator_user_id,
                "join_code_digest": digest,
                "active": True,
                "created_at": now,
                "updated_at": now,
            }

            membership = {
                "workspace_id": workspace["id"],
                "user_id": creator_user_id,
                "membership_role": "owner",
                "active": True,
                "joined_at": now,
                "added_by_user_id": creator_user_id,
            }

            try:
                with bootstrap_transaction(self.engine, user_id=creator_user_id) as connection:
                    connection.execute(
                        insert(
                            dbm.workspaces
                        ).values(
                            **workspace
                        )
                    )

                    # The freshly inserted, server-generated ID is trusted for
                    # the atomic first owner membership; no discovery bypass.
                    apply_tenant_session_context(
                        connection, workspace_id=workspace["id"], user_id=creator_user_id,
                    )
                    connection.execute(
                        insert(
                            dbm.organization_memberships
                        ).values(
                            **membership
                        )
                    )

                return workspace, join_code

            except IntegrityError:
                # A join-code digest collision can be retried safely because
                # the transaction rolls back both inserts.
                continue

        raise RuntimeError(
            "Could not generate a unique organization join code."
        )

    def join_organization(
        self,
        *,
        user_id: str,
        join_code: str,
    ):
        """Join one active Organization using its secret share code.

        Invalid and inactive codes intentionally resolve the same way so this
        method cannot be used as an Organization discovery mechanism.
        """

        user = self.get_user(
            user_id
        )

        if (
            user is None
            or not user["active"]
        ):
            raise ValueError(
                "Organization member is unavailable."
            )

        digest = join_code_digest(
            join_code
        )

        now = timestamp(
            datetime.now(timezone.utc)
        )

        with invitation_transaction(self.engine, user_id=user_id, digest=digest) as connection:
            workspace_row = connection.execute(
                select(
                    dbm.workspaces
                ).where(
                    dbm.workspaces.c.kind
                    == "organization",
                    dbm.workspaces.c.active.is_(True),
                    dbm.workspaces.c.join_code_digest
                    == digest,
                )
            ).mappings().first()

            if workspace_row is None:
                raise LookupError(
                    "Invalid organization join code."
                )

            workspace = dict(
                workspace_row
            )
            apply_invitation_membership_context(
                connection, user_id=user_id, workspace_id=workspace["id"], digest=digest,
            )

            membership_row = connection.execute(
                select(
                    dbm.organization_memberships
                ).where(
                    dbm.organization_memberships.c.workspace_id
                    == workspace["id"],
                    dbm.organization_memberships.c.user_id
                    == user_id,
                )
            ).mappings().first()

            if membership_row is not None:
                membership = dict(
                    membership_row
                )

                # Never downgrade an existing owner simply because they used
                # the join code again.
                role = membership[
                    "membership_role"
                ]

                if not membership["active"]:
                    connection.execute(
                        update(
                            dbm.organization_memberships
                        )
                        .where(
                            dbm.organization_memberships.c.workspace_id
                            == workspace["id"],
                            dbm.organization_memberships.c.user_id
                            == user_id,
                        )
                        .values(
                            active=True,
                            membership_role=role,
                            joined_at=now,
                            added_by_user_id=user_id,
                        )
                    )

                membership["active"] = True
                membership["joined_at"] = now
                membership[
                    "added_by_user_id"
                ] = user_id

                return workspace, membership

            membership = {
                "workspace_id": workspace["id"],
                "user_id": user_id,
                "membership_role": "member",
                "active": True,
                "joined_at": now,
                "added_by_user_id": user_id,
            }

            connection.execute(
                insert(
                    dbm.organization_memberships
                ).values(
                    **membership
                )
            )

            return workspace, membership

    def save_organization_membership(
        self,
        membership: dict,
    ):
        """Persist membership only for an active Organization workspace."""
        self._require_legacy_sqlite()

        workspace = self.get_workspace(
            membership["workspace_id"]
        )

        if workspace is None:
            raise ValueError(
                "Organization workspace does not exist."
            )

        if workspace["kind"] != "organization":
            raise ValueError(
                "Personal Workspaces cannot have organization memberships."
            )

        if not workspace["active"]:
            raise ValueError(
                "Organization workspace is inactive."
            )

        user = self.get_user(
            membership["user_id"]
        )

        if user is None or not user["active"]:
            raise ValueError(
                "Membership user is unavailable."
            )

        added_by = self.get_user(
            membership["added_by_user_id"]
        )

        if added_by is None or not added_by["active"]:
            raise ValueError(
                "Membership actor is unavailable."
            )

        with self.engine.begin() as connection:
            exists = connection.execute(
                select(
                    dbm.organization_memberships.c.workspace_id
                ).where(
                    dbm.organization_memberships.c.workspace_id
                    == membership["workspace_id"],
                    dbm.organization_memberships.c.user_id
                    == membership["user_id"],
                )
            ).first()

            if exists:
                connection.execute(
                    update(dbm.organization_memberships)
                    .where(
                        dbm.organization_memberships.c.workspace_id
                        == membership["workspace_id"],
                        dbm.organization_memberships.c.user_id
                        == membership["user_id"],
                    )
                    .values(**membership)
                )
            else:
                connection.execute(
                    insert(
                        dbm.organization_memberships
                    ).values(**membership)
                )

    def get_organization_membership(
        self,
        workspace_id: str,
        user_id: str,
        *,
        actor_user_id: str | None = None,
    ):
        if actor_user_id is not None:
            self.resolve_workspace_for_user(actor_user_id, workspace_id)
        transaction = (
            tenant_transaction(self.engine, workspace_id=workspace_id, user_id=actor_user_id)
            if actor_user_id is not None else bootstrap_transaction(self.engine, user_id=user_id)
        )
        with transaction as connection:
            row = connection.execute(
                select(
                    dbm.organization_memberships
                ).where(
                    dbm.organization_memberships.c.workspace_id
                    == workspace_id,
                    dbm.organization_memberships.c.user_id
                    == user_id,
                )
            ).mappings().first()

        return dict(row) if row else None

    def list_organization_memberships_for_user(
        self,
        user_id: str,
        *,
        active_only: bool = True,
    ):
        statement = (
            select(
                dbm.organization_memberships
            )
            .where(
                dbm.organization_memberships.c.user_id
                == user_id
            )
            .order_by(
                dbm.organization_memberships.c.joined_at,
                dbm.organization_memberships.c.workspace_id,
            )
        )

        if active_only:
            statement = statement.where(
                dbm.organization_memberships.c.active.is_(True)
            )

        with bootstrap_transaction(self.engine, user_id=user_id) as connection:
            rows = connection.execute(
                statement
            ).mappings().all()

        return [
            dict(row)
            for row in rows
        ]

    def list_organization_memberships(
        self,
        workspace_id: str,
        *,
        active_only: bool = True,
        actor_user_id: str | None = None,
    ):
        statement = (
            select(
                dbm.organization_memberships
            )
            .where(
                dbm.organization_memberships.c.workspace_id
                == workspace_id
            )
            .order_by(
                dbm.organization_memberships.c.joined_at,
                dbm.organization_memberships.c.user_id,
            )
        )

        if active_only:
            statement = statement.where(
                dbm.organization_memberships.c.active.is_(True)
            )

        if actor_user_id is None:
            self._require_legacy_sqlite()
        else:
            self.resolve_workspace_for_user(actor_user_id, workspace_id)
        transaction = (
            tenant_transaction(self.engine, workspace_id=workspace_id, user_id=actor_user_id)
            if actor_user_id is not None else self.engine.begin()
        )
        with transaction as connection:
            rows = connection.execute(
                statement
            ).mappings().all()

        return [
            dict(row)
            for row in rows
        ]

    def change_organization_membership_role(
        self,
        *,
        workspace_id: str,
        actor_user_id: str,
        target_user_id: str,
        new_role: str,
    ):
        """Change one active Organization membership role with RBAC safeguards.

        Role changes are organization-scoped and fail closed. Admin membership
        changes require an owner. Ownership changes also require an owner, and
        the final active owner can never be demoted.
        """

        from app.security.rbac import (
            AuthorizationError,
            Permission,
            WorkspaceAuthorization,
            WorkspaceRole,
        )

        try:
            requested_role = WorkspaceRole(new_role)
        except (TypeError, ValueError) as exc:
            raise ValueError("Unsupported organization role.") from exc

        # Resolve from user-bound discovery before carrying a selected workspace.
        # The atomic operation below still rechecks membership and IAM permissions.
        from app.security.rbac import resolve_workspace_authorization
        resolve_workspace_authorization(self, user_id=actor_user_id, workspace_id=workspace_id)
        with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=actor_user_id) as connection:
            workspace = connection.execute(
                select(dbm.workspaces).where(
                    dbm.workspaces.c.id == workspace_id
                )
            ).mappings().first()

            if (
                workspace is None
                or workspace["kind"] != "organization"
                or not workspace["active"]
            ):
                raise AuthorizationError("Permission denied.")

            actor = connection.execute(
                select(dbm.organization_memberships).where(
                    dbm.organization_memberships.c.workspace_id == workspace_id,
                    dbm.organization_memberships.c.user_id == actor_user_id,
                )
            ).mappings().first()

            target = connection.execute(
                select(dbm.organization_memberships).where(
                    dbm.organization_memberships.c.workspace_id == workspace_id,
                    dbm.organization_memberships.c.user_id == target_user_id,
                )
            ).mappings().first()

            if (
                actor is None
                or not actor["active"]
                or target is None
                or not target["active"]
            ):
                raise AuthorizationError("Permission denied.")

            try:
                actor_role = WorkspaceRole(actor["membership_role"])
                target_role = WorkspaceRole(target["membership_role"])
            except (TypeError, ValueError) as exc:
                raise AuthorizationError("Permission denied.") from exc

            authorization = WorkspaceAuthorization(
                user_id=actor_user_id,
                workspace_id=workspace_id,
                workspace_kind="organization",
                role=actor_role,
            )

            if (
                target_role is WorkspaceRole.OWNER
                or requested_role is WorkspaceRole.OWNER
            ):
                authorization.require(
                    Permission.ORGANIZATION_OWNERSHIP_MANAGE
                )
            elif (
                target_role is WorkspaceRole.ADMIN
                or requested_role is WorkspaceRole.ADMIN
            ):
                authorization.require(
                    Permission.ORGANIZATION_ADMINS_MANAGE
                )
            else:
                authorization.require(
                    Permission.ORGANIZATION_MEMBERS_MANAGE
                )

            if target_role is requested_role:
                return dict(target)

            if (
                target_role is WorkspaceRole.OWNER
                and requested_role is not WorkspaceRole.OWNER
            ):
                owner_count = connection.execute(
                    select(dbm.organization_memberships.c.user_id).where(
                        dbm.organization_memberships.c.workspace_id == workspace_id,
                        dbm.organization_memberships.c.membership_role == "owner",
                        dbm.organization_memberships.c.active.is_(True),
                    )
                ).all()

                if len(owner_count) <= 1:
                    raise ValueError(
                        "The last active organization owner cannot be demoted."
                    )

            connection.execute(
                update(dbm.organization_memberships)
                .where(
                    dbm.organization_memberships.c.workspace_id == workspace_id,
                    dbm.organization_memberships.c.user_id == target_user_id,
                    dbm.organization_memberships.c.active.is_(True),
                )
                .values(
                    membership_role=requested_role.value,
                    added_by_user_id=actor_user_id,
                )
            )

            updated = connection.execute(
                select(dbm.organization_memberships).where(
                    dbm.organization_memberships.c.workspace_id == workspace_id,
                    dbm.organization_memberships.c.user_id == target_user_id,
                )
            ).mappings().one()

            return dict(updated)

    @staticmethod
    def _hr_authorization_in_transaction(connection, *, workspace_id, actor_user_id):
        """Recheck the actor's current IAM boundary on the HR operation connection.

        Bootstrap resolution is still required before selecting this workspace;
        this check closes stale preflight decisions without caching HR/IAM roles.
        HR assignments never grant membership or IAM management permissions.
        """
        from app.security.rbac import AuthorizationError, WorkspaceAuthorization, WorkspaceRole

        workspace = connection.execute(select(dbm.workspaces).where(
            dbm.workspaces.c.id == workspace_id,
            dbm.workspaces.c.kind == "organization",
            dbm.workspaces.c.active.is_(True),
        )).mappings().first()
        actor = connection.execute(select(dbm.organization_memberships).where(
            dbm.organization_memberships.c.workspace_id == workspace_id,
            dbm.organization_memberships.c.user_id == actor_user_id,
            dbm.organization_memberships.c.active.is_(True),
        )).mappings().first()
        if workspace is None or actor is None:
            raise AuthorizationError("Permission denied.")
        try:
            role = WorkspaceRole(actor["membership_role"])
        except (TypeError, ValueError) as exc:
            raise AuthorizationError("Permission denied.") from exc
        return WorkspaceAuthorization(actor_user_id, workspace_id, "organization", role)

    def assign_organization_human_role(
        self,
        *,
        workspace_id: str,
        actor_user_id: str,
        target_user_id: str,
        human_role: str,
    ):
        """Assign or reactivate one HR-domain role for an Organization member."""

        from app.security.hr_roles import HRHumanRole
        from app.security.rbac import (
            AuthorizationError,
            Permission,
            resolve_workspace_authorization,
        )

        try:
            requested_role = HRHumanRole(human_role)
        except (TypeError, ValueError) as exc:
            raise ValueError("Unsupported HR human role.") from exc

        authorization = resolve_workspace_authorization(
            self,
            user_id=actor_user_id,
            workspace_id=workspace_id,
        )
        authorization.require(Permission.ORGANIZATION_HUMAN_ROLES_MANAGE)

        assignment = {
            "workspace_id": workspace_id,
            "user_id": target_user_id,
            "human_role": requested_role.value,
            "active": True,
            "assigned_at": timestamp(datetime.now(timezone.utc)),
            "assigned_by_user_id": actor_user_id,
        }

        with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=actor_user_id) as connection:
            self._hr_authorization_in_transaction(
                connection, workspace_id=workspace_id, actor_user_id=actor_user_id,
            ).require(Permission.ORGANIZATION_HUMAN_ROLES_MANAGE)
            target_membership = connection.execute(select(dbm.organization_memberships).where(
                dbm.organization_memberships.c.workspace_id == workspace_id,
                dbm.organization_memberships.c.user_id == target_user_id,
                dbm.organization_memberships.c.active.is_(True),
            )).mappings().first()
            if target_membership is None:
                raise AuthorizationError("Permission denied.")
            existing = connection.execute(
                select(dbm.organization_human_role_assignments).where(
                    dbm.organization_human_role_assignments.c.workspace_id
                    == workspace_id,
                    dbm.organization_human_role_assignments.c.user_id
                    == target_user_id,
                    dbm.organization_human_role_assignments.c.human_role
                    == requested_role.value,
                )
            ).mappings().first()

            if existing:
                connection.execute(
                    update(dbm.organization_human_role_assignments)
                    .where(
                        dbm.organization_human_role_assignments.c.workspace_id
                        == workspace_id,
                        dbm.organization_human_role_assignments.c.user_id
                        == target_user_id,
                        dbm.organization_human_role_assignments.c.human_role
                        == requested_role.value,
                    )
                    .values(**assignment)
                )
            else:
                connection.execute(
                    insert(dbm.organization_human_role_assignments).values(
                        **assignment
                    )
                )

        return assignment

    def deactivate_organization_human_role(
        self,
        *,
        workspace_id: str,
        actor_user_id: str,
        target_user_id: str,
        human_role: str,
    ):
        """Deactivate one HR-domain role without deleting assignment history."""

        from app.security.hr_roles import HRHumanRole
        from app.security.rbac import (
            Permission,
            resolve_workspace_authorization,
        )

        try:
            requested_role = HRHumanRole(human_role)
        except (TypeError, ValueError) as exc:
            raise ValueError("Unsupported HR human role.") from exc

        authorization = resolve_workspace_authorization(
            self,
            user_id=actor_user_id,
            workspace_id=workspace_id,
        )
        authorization.require(Permission.ORGANIZATION_HUMAN_ROLES_MANAGE)

        with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=actor_user_id) as connection:
            self._hr_authorization_in_transaction(
                connection, workspace_id=workspace_id, actor_user_id=actor_user_id,
            ).require(Permission.ORGANIZATION_HUMAN_ROLES_MANAGE)
            existing = connection.execute(
                select(dbm.organization_human_role_assignments).where(
                    dbm.organization_human_role_assignments.c.workspace_id
                    == workspace_id,
                    dbm.organization_human_role_assignments.c.user_id
                    == target_user_id,
                    dbm.organization_human_role_assignments.c.human_role
                    == requested_role.value,
                )
            ).mappings().first()

            if existing is None:
                return None

            connection.execute(
                update(dbm.organization_human_role_assignments)
                .where(
                    dbm.organization_human_role_assignments.c.workspace_id
                    == workspace_id,
                    dbm.organization_human_role_assignments.c.user_id
                    == target_user_id,
                    dbm.organization_human_role_assignments.c.human_role
                    == requested_role.value,
                )
                .values(
                    active=False,
                    assigned_at=timestamp(datetime.now(timezone.utc)),
                    assigned_by_user_id=actor_user_id,
                )
            )

            updated = connection.execute(
                select(dbm.organization_human_role_assignments).where(
                    dbm.organization_human_role_assignments.c.workspace_id
                    == workspace_id,
                    dbm.organization_human_role_assignments.c.user_id
                    == target_user_id,
                    dbm.organization_human_role_assignments.c.human_role
                    == requested_role.value,
                )
            ).mappings().one()

        return dict(updated)

    def list_organization_human_roles(
        self,
        workspace_id: str,
        *,
        user_id: str | None = None,
        active_only: bool = True,
        actor_user_id: str | None = None,
    ):
        """Read own active roles, or IAM-manager assignment history, in one tenant.

        user_id is the target filter, NOT the authenticated actor. Unscoped calls
        are SQLite fixture compatibility only and fail before PostgreSQL checkout.
        """
        from app.security.rbac import Permission, resolve_workspace_authorization

        if actor_user_id is None:
            self._require_legacy_sqlite()
        else:
            resolve_workspace_authorization(
                self, user_id=actor_user_id, workspace_id=workspace_id,
            )
        statement = select(dbm.organization_human_role_assignments).where(
            dbm.organization_human_role_assignments.c.workspace_id
            == workspace_id
        )

        if user_id is not None:
            statement = statement.where(
                dbm.organization_human_role_assignments.c.user_id == user_id
            )

        if active_only:
            statement = statement.where(
                dbm.organization_human_role_assignments.c.active.is_(True)
            )

        statement = statement.order_by(
            dbm.organization_human_role_assignments.c.user_id,
            dbm.organization_human_role_assignments.c.human_role,
        )

        transaction = (
            tenant_transaction(self.engine, workspace_id=workspace_id, user_id=actor_user_id)
            if actor_user_id is not None else self.engine.begin()
        )
        with transaction as connection:
            if actor_user_id is not None:
                authorization = self._hr_authorization_in_transaction(
                    connection, workspace_id=workspace_id, actor_user_id=actor_user_id,
                )
                if user_id != actor_user_id or not active_only:
                    authorization.require(Permission.ORGANIZATION_HUMAN_ROLES_MANAGE)
            rows = connection.execute(statement).mappings().all()

        return [dict(row) for row in rows]

    def save_auth_session(self, session: dict):
        """Persist only a digest of the browser's opaque session token."""

        with self.engine.begin() as connection:
            self._upsert(
                connection,
                dbm.auth_sessions,
                "id",
                session,
            )

    def get_auth_session_by_digest(self, token_digest: str):
        with self.engine.connect() as connection:
            row = connection.execute(
                select(dbm.auth_sessions).where(
                    dbm.auth_sessions.c.token_digest == token_digest
                )
            ).mappings().first()

        return dict(row) if row else None

    def revoke_auth_session(
        self,
        session_id: str,
        revoked_at: str,
    ):
        with self.engine.begin() as connection:
            connection.execute(
                update(dbm.auth_sessions)
                .where(dbm.auth_sessions.c.id == session_id)
                .values(revoked_at=revoked_at)
            )

    def save_agent(self, agent):
        with self.engine.begin() as connection:
            self._upsert(connection, dbm.agent_roster, "id", dict(
                id=agent.id, payload=agent.model_dump(mode="json")))

    def agents(self):
        with self.engine.connect() as connection:
            return connection.execute(select(dbm.agent_roster.c.payload)).scalars().all()

    def save_dataset(self, dataset: dict):
        with self.engine.begin() as connection:
            self._upsert(connection, dbm.dataset_registry, "dataset_id", dataset)

    def save_datasets(self, datasets: list[dict]):
        with self.engine.begin() as connection:
            for dataset in datasets:
                self._upsert(connection, dbm.dataset_registry, "dataset_id", dataset)

    def get_dataset(self, dataset_id: str):
        with self.engine.connect() as connection:
            row = connection.execute(select(dbm.dataset_registry).where(
                dbm.dataset_registry.c.dataset_id == dataset_id)).mappings().first()
        return dict(row) if row else None

    def list_datasets(self):
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(select(dbm.dataset_registry).order_by(
                dbm.dataset_registry.c.family, dbm.dataset_registry.c.record_count)).mappings()]


repository = Repository(settings.DATABASE_URL)
