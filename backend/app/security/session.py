"""Opaque application-session and OAuth transaction primitives."""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone


SESSION_COOKIE_NAME = "app_session"

OAUTH_STATE_COOKIE = "oauth_state"
OAUTH_NONCE_COOKIE = "oauth_nonce"
OAUTH_PKCE_COOKIE = "oauth_pkce"

OAUTH_TRANSACTION_SECONDS = 600
SESSION_HOURS = 12


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    if not token:
        raise ValueError("Session token must not be empty.")

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def create_pkce_pair() -> tuple[str, str]:
    """Return RFC 7636 verifier + S256 challenge."""

    verifier = secrets.token_urlsafe(64)

    challenge_bytes = hashlib.sha256(
        verifier.encode("ascii")
    ).digest()

    challenge = (
        base64.urlsafe_b64encode(
            challenge_bytes
        )
        .decode("ascii")
        .rstrip("=")
    )

    return verifier, challenge


def session_expiry() -> datetime:
    return utcnow() + timedelta(
        hours=SESSION_HOURS
    )


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed
