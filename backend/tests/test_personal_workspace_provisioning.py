"""Phase 4.2.3 automatic Personal Workspace provisioning tests."""

from datetime import datetime, timezone

from sqlalchemy import select

from app.storage import models as dbm
from app.storage.database import Repository


def make_user(
    user_id: str,
    google_sub: str,
):
    now = datetime.now(
        timezone.utc
    ).isoformat()

    return {
        "id": user_id,
        "google_sub": google_sub,
        "email": f"{user_id.lower()}@example.com",
        "display_name": user_id,
        "profile_picture": None,
        "email_verified": True,
        "active": True,
        "created_at": now,
        "last_login_at": now,
    }


def test_new_user_receives_private_personal_workspace(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'new-user.db'}"
    )
    repo.initialize()

    user = make_user(
        "USR-new",
        "google-new",
    )

    repo.save_user(user)

    workspace = repo.ensure_personal_workspace(
        user["id"]
    )

    assert workspace["kind"] == "personal"
    assert workspace["name"] == "Personal Workspace"
    assert (
        workspace["personal_owner_user_id"]
        == user["id"]
    )
    assert (
        workspace["created_by_user_id"]
        == user["id"]
    )
    assert workspace["join_code_digest"] is None
    assert workspace["active"] is True


def test_two_users_receive_different_personal_workspaces(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'two-users.db'}"
    )
    repo.initialize()

    first_user = make_user(
        "USR-first",
        "google-first",
    )

    second_user = make_user(
        "USR-second",
        "google-second",
    )

    repo.save_user(first_user)
    repo.save_user(second_user)

    first_workspace = (
        repo.ensure_personal_workspace(
            first_user["id"]
        )
    )

    second_workspace = (
        repo.ensure_personal_workspace(
            second_user["id"]
        )
    )

    assert (
        first_workspace["id"]
        != second_workspace["id"]
    )

    assert (
        first_workspace[
            "personal_owner_user_id"
        ]
        == first_user["id"]
    )

    assert (
        second_workspace[
            "personal_owner_user_id"
        ]
        == second_user["id"]
    )


def test_existing_user_without_workspace_is_backfilled(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'backfill.db'}"
    )
    repo.initialize()

    user = make_user(
        "USR-existing",
        "google-existing",
    )

    repo.save_user(user)

    assert (
        repo.get_personal_workspace(
            user["id"]
        )
        is None
    )

    created = repo.ensure_personal_workspace(
        user["id"]
    )

    assert created is not None

    restored = repo.get_personal_workspace(
        user["id"]
    )

    assert restored["id"] == created["id"]


def test_repeated_provisioning_never_creates_duplicate(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'repeat.db'}"
    )
    repo.initialize()

    user = make_user(
        "USR-repeat",
        "google-repeat",
    )

    repo.save_user(user)

    ids = {
        repo.ensure_personal_workspace(
            user["id"]
        )["id"]
        for _ in range(5)
    }

    assert len(ids) == 1

    with repo.engine.connect() as connection:
        rows = connection.execute(
            select(dbm.workspaces).where(
                dbm.workspaces.c.personal_owner_user_id
                == user["id"]
            )
        ).all()

    assert len(rows) == 1


def test_personal_workspace_is_not_an_organization_membership(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'no-membership.db'}"
    )
    repo.initialize()

    user = make_user(
        "USR-private",
        "google-private",
    )

    repo.save_user(user)

    workspace = repo.ensure_personal_workspace(
        user["id"]
    )

    assert workspace["kind"] == "personal"

    assert (
        repo.list_organization_memberships_for_user(
            user["id"]
        )
        == []
    )
