"""SQLite snapshot repository. One transaction persists a run and all nested records.

Schema migrations use PRAGMA user_version. SQL is isolated here so a future
PostgreSQL repository can retain the same interface. No credentials are stored.
"""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.core.config import settings
from app.models.schemas import Task, UploadedContext


class Repository:
    def __init__(self, url: str):
        if not url.startswith("sqlite:///"):
            raise ValueError("V1 persistence requires a sqlite:/// DATABASE_URL")
        self.path = url.removeprefix("sqlite:///")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise RuntimeError("Database schema is newer than this application")
            db.execute("""CREATE TABLE IF NOT EXISTS simulations (
                id TEXT PRIMARY KEY, owner_id TEXT, status TEXT NOT NULL,
                created_at TEXT NOT NULL, payload TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS uploads (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS agent_roster (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL)""")
            db.execute("PRAGMA user_version=1")

    def save(self, task: Task):
        with self.connect() as db:
            db.execute("""INSERT INTO simulations VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET owner_id=excluded.owner_id,
                status=excluded.status, payload=excluded.payload""",
                (task.id, task.owner_id, task.status.value,
                 (task.created_at or task.started_at).isoformat(), task.model_dump_json()))

    def get(self, task_id: str):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM simulations WHERE id=?", (task_id,)).fetchone()
        return Task.model_validate_json(row[0]) if row else None

    def list(self):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM simulations ORDER BY created_at, id").fetchall()
        return [Task.model_validate_json(row[0]) for row in rows]

    def save_upload(self, upload: UploadedContext):
        with self.connect() as db:
            db.execute("INSERT INTO uploads VALUES (?, ?)", (upload.id, upload.model_dump_json()))

    def get_upload(self, upload_id: str):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM uploads WHERE id=?", (upload_id,)).fetchone()
        return UploadedContext.model_validate_json(row[0]) if row else None

    def save_agent(self, agent):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO agent_roster VALUES (?, ?)", (agent.id, agent.model_dump_json()))

    def agents(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT payload FROM agent_roster")]


repository = Repository(settings.DATABASE_URL)
