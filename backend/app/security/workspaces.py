"""Workspace and organization security primitives."""

from __future__ import annotations

import hashlib
import secrets


# Excludes visually ambiguous characters such as 0/O and 1/I.
_JOIN_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
_JOIN_GROUP_SIZE = 4
_JOIN_GROUPS = 3


def generate_join_code() -> str:
    """Create a human-shareable cryptographically random organization code."""

    groups = [
        "".join(
            secrets.choice(_JOIN_ALPHABET)
            for _ in range(_JOIN_GROUP_SIZE)
        )
        for _ in range(_JOIN_GROUPS)
    ]

    return "-".join(groups)


def normalize_join_code(value: str) -> str:
    """Normalize user-entered codes without weakening their entropy."""

    return value.strip().upper()


def join_code_digest(value: str) -> str:
    """Return the only representation of a join code stored in the database."""

    normalized = normalize_join_code(value)

    if not normalized:
        raise ValueError(
            "Join code must not be empty."
        )

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()
