"""Opaque application-session and OAuth transaction primitives."""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone


SESSION_COOKIE_NAME = "app_session"

OAUTH_STATE_COOKIE = "oauth_state"
OAUTH_NONCE_COOKIE = "oauth_nonce"
OAUTH_PKCE_COOKIE = "oauth_pkce"
OAUTH_TRANSACTION_COOKIE_PREFIX = "oauth_tx_"


def oauth_cookie_name(state: str) -> str:
    return OAUTH_TRANSACTION_COOKIE_PREFIX + token_digest(state)


class OAuthAccessLogFilter(logging.Filter):
    """Uvicorn must not record callback codes/state or other auth queries."""

    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            path = record.args[2]
            if isinstance(path, str) and path.startswith("/api/v1/auth/"):
                args = list(record.args)
                args[2] = path.split("?", 1)[0]
                record.args = tuple(args)
        return True


def protect_oauth_access_logs():
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, OAuthAccessLogFilter) for item in logger.filters):
        logger.addFilter(OAuthAccessLogFilter())

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
