"""Phase 4.2.4 current-workspace resolution tests."""

from datetime import datetime, timezone

import pytest

from app.storage.database import Repository


def now_text():
    return datetime.now(
        timezone.utc
    ).isoformat()


def make_user(
    user_id: str,
    google_sub: str,
):
    now = now_text()

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


def make_organization(
    owner_id: str,
    workspace_id: str,
):
    now = now_text()

    return {
        "id": workspace_id,
        "kind": "organization",
        "name": "Example Organization",
        "personal_owner_user_id": None,
        "created_by_user_id": owner_id,
        "join_code_digest": None,
        "active": True,
        "created_at": now,
        "updated_at": now,
    }


def make_membership(
    workspace_id: str,
    user_id: str,
    *,
    role: str = "member",
    active: bool = True,
    added_by: str,
):
    return {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "membership_role": role,
        "active": active,
        "joined_at": now_text(),
        "added_by_user_id": added_by,
    }


def test_default_resolution_returns_personal_workspace(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'default.db'}"
    )
    repo.initialize()

    user = make_user(
        "USR-a",
        "google-a",
    )

    repo.save_user(user)

    resolved = repo.resolve_workspace_for_user(
        user["id"]
    )

    assert resolved["kind"] == "personal"
    assert (
        resolved["personal_owner_user_id"]
        == user["id"]
    )


def test_user_can_resolve_own_personal_workspace(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'personal.db'}"
    )
    repo.initialize()

    user = make_user(
        "USR-a",
        "google-a",
    )
    repo.save_user(user)

    personal = repo.ensure_personal_workspace(
        user["id"]
    )

    resolved = repo.resolve_workspace_for_user(
        user["id"],
        personal["id"],
    )

    assert resolved["id"] == personal["id"]


def test_user_cannot_resolve_another_users_personal_workspace(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'other-personal.db'}"
    )
    repo.initialize()

    first = make_user(
        "USR-a",
        "google-a",
    )
    second = make_user(
        "USR-b",
        "google-b",
    )

    repo.save_user(first)
    repo.save_user(second)

    other_workspace = (
        repo.ensure_personal_workspace(
            second["id"]
        )
    )

    with pytest.raises(
        PermissionError,
        match="access denied",
    ):
        repo.resolve_workspace_for_user(
            first["id"],
            other_workspace["id"],
        )


def test_active_org_member_can_resolve_organization(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'org-member.db'}"
    )
    repo.initialize()

    owner = make_user(
        "USR-owner",
        "google-owner",
    )
    member = make_user(
        "USR-member",
        "google-member",
    )

    repo.save_user(owner)
    repo.save_user(member)

    organization = make_organization(
        owner["id"],
        "WS-org",
    )

    repo.save_workspace(organization)

    repo.save_organization_membership(
        make_membership(
            organization["id"],
            member["id"],
            added_by=owner["id"],
        )
    )

    resolved = repo.resolve_workspace_for_user(
        member["id"],
        organization["id"],
    )

    assert resolved["id"] == organization["id"]
    assert resolved["kind"] == "organization"


def test_nonmember_cannot_resolve_organization(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'nonmember.db'}"
    )
    repo.initialize()

    owner = make_user(
        "USR-owner",
        "google-owner",
    )
    outsider = make_user(
        "USR-outsider",
        "google-outsider",
    )

    repo.save_user(owner)
    repo.save_user(outsider)

    organization = make_organization(
        owner["id"],
        "WS-org",
    )

    repo.save_workspace(organization)

    with pytest.raises(
        PermissionError,
        match="access denied",
    ):
        repo.resolve_workspace_for_user(
            outsider["id"],
            organization["id"],
        )


def test_inactive_membership_cannot_resolve_organization(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'inactive-member.db'}"
    )
    repo.initialize()

    owner = make_user(
        "USR-owner",
        "google-owner",
    )
    member = make_user(
        "USR-member",
        "google-member",
    )

    repo.save_user(owner)
    repo.save_user(member)

    organization = make_organization(
        owner["id"],
        "WS-org",
    )

    repo.save_workspace(organization)

    repo.save_organization_membership(
        make_membership(
            organization["id"],
            member["id"],
            active=False,
            added_by=owner["id"],
        )
    )

    with pytest.raises(
        PermissionError,
        match="access denied",
    ):
        repo.resolve_workspace_for_user(
            member["id"],
            organization["id"],
        )


def test_unknown_workspace_is_not_discoverable(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'unknown.db'}"
    )
    repo.initialize()

    user = make_user(
        "USR-a",
        "google-a",
    )

    repo.save_user(user)

    with pytest.raises(
        PermissionError,
        match="unavailable",
    ):
        repo.resolve_workspace_for_user(
            user["id"],
            "WS-does-not-exist",
        )
