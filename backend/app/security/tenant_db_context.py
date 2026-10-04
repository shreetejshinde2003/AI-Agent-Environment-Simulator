"""Trusted transaction-scoped tenant context for PostgreSQL RLS.

The application remains responsible for authenticating the user and resolving an
accessible workspace before opening a tenant transaction.  This module carries
that already-authorized identity into PostgreSQL using transaction-local custom
settings. Data-plane RLS policies read those settings with ``current_setting``.
Startup maintenance uses an explicit system principal and workspace IDs from the
trusted catalog; it never impersonates an authenticated user or bypasses RLS.

SQLite intentionally receives no database session variables so local development
and the existing SQLite test suite continue to work.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


WORKSPACE_SETTING = "app.current_workspace_id"
USER_SETTING = "app.current_user_id"

# Missing settings return NULL rather than raising.  RLS policies must compare
# tenant columns against these expressions so an unset context matches nothing.
CURRENT_WORKSPACE_SQL = (
    "NULLIF(current_setting('app.current_workspace_id', true), '')"
)
CURRENT_USER_SQL = "NULLIF(current_setting('app.current_user_id', true), '')"


class TenantContextError(ValueError):
    """Raised before a transaction is opened for an invalid tenant context."""


def _validate_context_value(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise TenantContextError(f"{field} must be a string")
    if not value or value != value.strip():
        raise TenantContextError(f"{field} must be a non-empty canonical identifier")
    if "\x00" in value:
        raise TenantContextError(f"{field} contains an invalid character")
    if len(value) > 255:
        raise TenantContextError(f"{field} is too long")
    return value


@dataclass(frozen=True, slots=True)
class TenantSessionContext:
    """Already-authorized application identity carried into one DB transaction."""

    workspace_id: str
    user_id: str

    @classmethod
    def validated(cls, *, workspace_id: str, user_id: str) -> "TenantSessionContext":
        return cls(
            workspace_id=_validate_context_value(workspace_id, "workspace_id"),
            user_id=_validate_context_value(user_id, "user_id"),
        )


def apply_tenant_session_context(
    connection: Connection,
    *,
    workspace_id: str,
    user_id: str,
) -> TenantSessionContext:
    """Set trusted tenant identity on an existing transaction.

    PostgreSQL uses ``set_config(..., true)``.  The final ``true`` is essential:
    it makes each setting LOCAL to the current transaction rather than leaking it
    through a pooled connection into a later request.

    SQLite validates the same context but otherwise performs no operation.
    """

    context = TenantSessionContext.validated(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    if connection.dialect.name != "postgresql":
        return context

    connection.execute(
        text(
            "SELECT "
            "set_config(:workspace_setting, :workspace_id, true), "
            "set_config(:user_setting, :user_id, true)"
        ),
        {
            "workspace_setting": WORKSPACE_SETTING,
            "workspace_id": context.workspace_id,
            "user_setting": USER_SETTING,
            "user_id": context.user_id,
        },
    )
    return context


@contextmanager
def tenant_transaction(
    engine: Engine,
    *,
    workspace_id: str,
    user_id: str,
) -> Iterator[Connection]:
    """Open one transaction carrying the trusted tenant context.

    Callers must pass identities obtained from authenticated workspace resolution
    or trusted startup maintenance, never raw client-supplied IDs. Validation
    occurs before ``engine.begin()`` so
    malformed/missing identity cannot open a tenant transaction.
    """

    context = TenantSessionContext.validated(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    with engine.begin() as connection:
        apply_tenant_session_context(
            connection,
            workspace_id=context.workspace_id,
            user_id=context.user_id,
        )
        yield connection
