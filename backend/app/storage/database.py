"""Operational persistence with SQLite fallback and PostgreSQL support.

V1 SQLite snapshots are backed up, archived, and projected into the
current relational schema. Version 3 adds local Google identities and
revocable application sessions without changing existing simulation payloads.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, delete, event, insert, select, update

from app.core.config import settings
from app.models.schemas import Task, UploadedContext
from app.storage import models as dbm

SCHEMA_VERSION = 3


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

    def initialize(self):
        engine = self.engine
        if engine.dialect.name == "sqlite":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            self._initialize_sqlite()
        else:
            with engine.begin() as connection:
                # Serialize concurrent Railway workers during startup/migration.
                connection.exec_driver_sql("SELECT pg_advisory_xact_lock(721842)")

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

                elif versions == [2]:
                    # V3 is additive: users + auth_sessions. create_all above
                    # safely creates the new tables while preserving all V2
                    # simulation/benchmark data.
                    connection.execute(
                        update(dbm.schema_version)
                        .where(dbm.schema_version.c.version == 2)
                        .values(
                            version=SCHEMA_VERSION,
                            applied_at=timestamp(datetime.now(timezone.utc)),
                        )
                    )

                elif versions != [SCHEMA_VERSION]:
                    raise RuntimeError(
                        "Unsupported PostgreSQL schema version"
                    )

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

            elif versions == [2]:
                connection.execute(
                    update(dbm.schema_version)
                    .where(dbm.schema_version.c.version == 2)
                    .values(
                        version=SCHEMA_VERSION,
                        applied_at=timestamp(datetime.now(timezone.utc)),
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
            id=task.id, owner_id=task.owner_id, dataset_id=task.dataset_id,
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
        with self.engine.begin() as connection:
            self._save_task(connection, task)

    def get(self, task_id: str):
        with self.engine.connect() as connection:
            payload = connection.execute(select(dbm.simulations.c.payload).where(dbm.simulations.c.id == task_id)).scalar_one_or_none()
        return Task.model_validate(payload) if payload is not None else None

    def list(self):
        with self.engine.connect() as connection:
            rows = connection.execute(select(dbm.simulations.c.payload).order_by(
                dbm.simulations.c.created_at, dbm.simulations.c.id)).scalars().all()
        return [Task.model_validate(row) for row in rows]

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
