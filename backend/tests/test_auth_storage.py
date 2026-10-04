"""Phase 4.1 authentication persistence tests.

No Google request, browser, provider credential or external PostgreSQL server
is used here.
"""

import sqlite3
from datetime import datetime, timedelta, timezone

from sqlalchemy import inspect, insert, select

from app.storage import models as dbm
from app.storage.database import Repository, SCHEMA_VERSION


def utc_text(value):
    return value.isoformat()


def make_user(now):
    return {
        "id": "USR-test",
        "google_sub": "google-sub-123",
        "email": "person@example.com",
        "display_name": "Test Person",
        "profile_picture": "https://example.com/avatar.png",
        "email_verified": True,
        "active": True,
        "created_at": utc_text(now),
        "last_login_at": utc_text(now),
    }


def make_session(now):
    return {
        "id": "SES-test",
        "user_id": "USR-test",
        "token_digest": "a" * 64,
        "created_at": utc_text(now),
        "expires_at": utc_text(now + timedelta(hours=12)),
        "revoked_at": None,
    }


def test_fresh_database_contains_auth_tables(tmp_path):
    repo = Repository(
        f"sqlite:///{tmp_path / 'auth.db'}"
    )

    repo.initialize()

    names = set(
        inspect(repo.engine).get_table_names()
    )

    assert "users" in names
    assert "auth_sessions" in names

    with sqlite3.connect(repo.path) as connection:
        assert (
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
            == SCHEMA_VERSION
            == 7
        )


def test_google_identity_round_trip(tmp_path):
    repo = Repository(
        f"sqlite:///{tmp_path / 'identity.db'}"
    )

    repo.initialize()

    now = datetime.now(timezone.utc)
    user = make_user(now)

    repo.save_user(user)

    by_id = repo.get_user(user["id"])
    by_google = repo.get_user_by_google_sub(
        user["google_sub"]
    )

    assert by_id == by_google
    assert by_id["email"] == "person@example.com"
    assert by_id["email_verified"] is True
    assert by_id["active"] is True


def test_google_identity_can_update_login_profile(tmp_path):
    repo = Repository(
        f"sqlite:///{tmp_path / 'identity-update.db'}"
    )

    repo.initialize()

    now = datetime.now(timezone.utc)
    user = make_user(now)

    repo.save_user(user)

    later = now + timedelta(minutes=10)

    updated = dict(
        user,
        display_name="Updated Person",
        profile_picture=None,
        last_login_at=utc_text(later),
    )

    repo.save_user(updated)

    restored = repo.get_user(user["id"])

    assert restored["google_sub"] == user["google_sub"]
    assert restored["display_name"] == "Updated Person"
    assert restored["profile_picture"] is None
    assert restored["last_login_at"] == utc_text(later)


def test_auth_session_stores_digest_and_can_be_revoked(tmp_path):
    repo = Repository(
        f"sqlite:///{tmp_path / 'session.db'}"
    )

    repo.initialize()

    now = datetime.now(timezone.utc)

    repo.save_user(
        make_user(now)
    )

    session = make_session(now)

    repo.save_auth_session(session)

    restored = repo.get_auth_session_by_digest(
        session["token_digest"]
    )

    assert restored["id"] == session["id"]
    assert restored["user_id"] == "USR-test"
    assert restored["token_digest"] == "a" * 64
    assert restored["revoked_at"] is None

    revoked_at = utc_text(
        now + timedelta(minutes=1)
    )

    repo.revoke_auth_session(
        session["id"],
        revoked_at,
    )

    restored = repo.get_auth_session_by_digest(
        session["token_digest"]
    )

    assert restored["revoked_at"] == revoked_at


def test_deleting_user_cascades_sessions(tmp_path):
    repo = Repository(
        f"sqlite:///{tmp_path / 'cascade.db'}"
    )

    repo.initialize()

    now = datetime.now(timezone.utc)

    repo.save_user(
        make_user(now)
    )

    repo.save_auth_session(
        make_session(now)
    )

    with repo.engine.begin() as connection:
        connection.execute(
            dbm.users.delete().where(
                dbm.users.c.id == "USR-test"
            )
        )

    with repo.engine.connect() as connection:
        sessions = connection.execute(
            select(dbm.auth_sessions)
        ).all()

    assert sessions == []


def test_schema_v2_database_migrates_additively_to_v7(tmp_path):
    path = tmp_path / "v2.db"

    # Construct a realistic V2 database using the current table metadata
    # but deliberately omit the new V3 auth tables.
    old_tables = [
        dbm.schema_version,
        dbm.dataset_registry,
        dbm.simulations,
        dbm.tasks,
        dbm.agent_executions,
        dbm.agent_messages,
        dbm.activity_events,
        dbm.run_events,
        dbm.simulation_metrics,
        dbm.uploads,
        dbm.simulation_uploads,
        dbm.agent_roster,
    ]

    repo = Repository(
        f"sqlite:///{path}"
    )

    with repo.engine.begin() as connection:
        for table in old_tables:
            table.create(
                connection,
                checkfirst=True,
            )

        connection.execute(
            insert(dbm.schema_version).values(
                version=2,
                applied_at="2026-09-29T00:00:00+00:00",
            )
        )

    with sqlite3.connect(path) as connection:
        connection.execute(
            "PRAGMA user_version=2"
        )

    repo.initialize()

    names = set(
        inspect(repo.engine).get_table_names()
    )

    assert "users" in names
    assert "auth_sessions" in names

    with repo.engine.connect() as connection:
        version = connection.execute(
            select(dbm.schema_version.c.version)
        ).scalar_one()

    assert version == SCHEMA_VERSION == 7

    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
            == SCHEMA_VERSION
            == 7
        )


def test_auth_schema_does_not_store_password_or_google_tokens():
    user_columns = {
        column.name
        for column in dbm.users.columns
    }

    session_columns = {
        column.name
        for column in dbm.auth_sessions.columns
    }

    forbidden = {
        "password",
        "password_hash",
        "access_token",
        "refresh_token",
        "id_token",
        "client_secret",
    }

    assert user_columns.isdisjoint(forbidden)
    assert session_columns.isdisjoint(forbidden)

    assert "google_sub" in user_columns
    assert "token_digest" in session_columns
