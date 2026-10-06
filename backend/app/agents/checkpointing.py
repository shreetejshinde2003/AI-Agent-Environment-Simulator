"""Task-bound PostgreSQL checkpoints; application evidence stays authoritative."""
from contextlib import asynccontextmanager
import hashlib
import json
import re

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection, Error as PostgresError, sql
from psycopg.rows import dict_row

from app.agents.execution_context import ExecutionContext
from app.security.rbac import AuthorizationError, Permission, resolve_workspace_authorization


class CheckpointBusyError(RuntimeError):
    """A second worker must leave the running task's evidence untouched."""


def checkpoint_connection_string(database_url: str) -> str:
    for prefix in ("postgresql+psycopg://", "postgres://", "postgresql://"):
        if database_url.startswith(prefix):
            return "postgresql://" + database_url.removeprefix(prefix)
    raise ValueError("LangGraph PostgreSQL checkpointing requires PostgreSQL.")


def checkpoint_thread_id(*, task_id: str, workspace_id: str | None) -> str:
    if not task_id or not task_id.strip():
        raise ValueError("Checkpoint task_id cannot be blank.")
    if not workspace_id or not workspace_id.strip():
        raise AuthorizationError("Checkpoint workspace is required.")
    identity = json.dumps([workspace_id, task_id], separators=(",", ":"))
    return "fm-v1-" + hashlib.sha256(identity.encode()).hexdigest()


def checkpoint_config(*, task_id: str, workspace_id: str | None) -> dict:
    return {"configurable": {"thread_id": checkpoint_thread_id(
        task_id=task_id, workspace_id=workspace_id)}}


def authorize_checkpoint(repository, *, task_id, workspace_id, user_id):
    if not user_id or not workspace_id or not task_id:
        raise AuthorizationError("Checkpoint identity is required.")
    resolve_workspace_authorization(repository, user_id=user_id,
        workspace_id=workspace_id).require(Permission.SIMULATION_CREATE)
    task = repository.get_for_tenant(task_id, workspace_id=workspace_id, user_id=user_id)
    if task is None or task.workspace_id != workspace_id:
        raise AuthorizationError("Checkpoint task is not visible.")
    return task


class ContextSerializer:
    """Data-only JSON, with a single explicitly validated Pydantic type.

    No pickle, dynamic imports, or arbitrary object construction from storage.
    Graphs here do not use custom Send objects or arbitrary message classes.
    """
    def dumps_typed(self, obj):
        def encode(value):
            if isinstance(value, ExecutionContext):
                return {"__fm_execution_context_v1__": value.model_dump(mode="json")}
            raise TypeError("Unsupported checkpoint value")
        return "json", json.dumps(obj, default=encode).encode()

    def loads_typed(self, data):
        kind, payload = data
        if kind != "json":
            raise ValueError("Unsupported checkpoint encoding")
        def decode(value):
            if set(value) == {"__fm_execution_context_v1__"}:
                try:
                    return ExecutionContext.model_validate(value["__fm_execution_context_v1__"])
                except ValueError:
                    raise ValueError('Checkpoint execution context is invalid.') from None
            return value
        return json.loads(payload, object_hook=decode)


class AuthorizedPostgresSaver(AsyncPostgresSaver):
    """One authenticated task per connection, reauthorized for every operation.

    The transaction-local setting is deliberately set on Psycopg's connection,
    never inherited from SQLAlchemy. FORCE RLS constrains every saver query.
    """
    def __init__(self, conn, *, repository, task_id, workspace_id, user_id):
        super().__init__(conn, serde=ContextSerializer())
        self.repository = repository
        self.identity = dict(task_id=task_id, workspace_id=workspace_id, user_id=user_id)
        self.thread_id = checkpoint_thread_id(task_id=task_id, workspace_id=workspace_id)

    @asynccontextmanager
    async def _cursor(self, *, pipeline=False):
        authorize_checkpoint(self.repository, **self.identity)
        try:
            async with self.lock, self.conn.transaction():
                async with self.conn.cursor(binary=True, row_factory=dict_row) as cur:
                    await cur.execute("SELECT set_config('app.checkpoint_thread_id', %s, true)",
                                      (self.thread_id,))
                    yield cur
        except PostgresError:
            raise RuntimeError('Checkpoint database operation failed.') from None

    async def setup(self):
        raise PermissionError("Checkpoint migrations must run separately from runtime.")

    def _check_config(self, config):
        values = (config or {}).get('configurable', {})
        if values.get('thread_id') != self.thread_id or values.get('checkpoint_ns', ''):
            raise AuthorizationError('Checkpoint thread or namespace mismatch.')
        authorize_checkpoint(self.repository, **self.identity)

    async def aget_tuple(self, config):
        self._check_config(config)
        return await super().aget_tuple(config)

    async def aput(self, config, checkpoint, metadata, new_versions):
        self._check_config(config)
        return await super().aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=''):
        self._check_config(config)
        return await super().aput_writes(config, writes, task_id, task_path)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        self._check_config(config)
        if before is not None:
            self._check_config(before)
        async for value in super().alist(config, filter=filter, before=before, limit=limit):
            yield value

    async def adelete_thread(self, thread_id):
        if thread_id != self.thread_id:
            raise AuthorizationError("Checkpoint thread mismatch.")
        await super().adelete_thread(thread_id)


async def verify_checkpoint_connection(conn, schema):
    """Reject bypass roles, migration owners, missing policies, and schema drift."""
    async with conn.cursor() as cur:
        await cur.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
        role = await cur.fetchone()
        if not role or role['rolsuper'] or role['rolbypassrls']:
            raise PermissionError("Checkpoint runtime must not bypass RLS.")
        await cur.execute("SELECT has_schema_privilege(current_user,%s,'CREATE') AS allowed", (schema,))
        if (await cur.fetchone())['allowed']:
            raise PermissionError("Checkpoint runtime must not have migration privileges.")
        await cur.execute("""SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,
            pg_has_role(current_user,c.relowner,'MEMBER') AS owns
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname=%s AND c.relname=ANY(%s)""",
            (schema, ['checkpoints', 'checkpoint_blobs', 'checkpoint_writes']))
        rows = await cur.fetchall()
        if len(rows) != 3 or any(r['owns'] or not r['relrowsecurity'] or not r['relforcerowsecurity'] for r in rows):
            raise PermissionError("Checkpoint tables require FORCE RLS and a separate runtime role.")
        # Extra permissive policies could silently widen access; require exact reviewed policy.
        await cur.execute("""SELECT c.relname,p.polname,pg_get_expr(p.polqual,p.polrelid) AS using_expr,
            pg_get_expr(p.polwithcheck,p.polrelid) AS check_expr
            FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s""", (schema,))
        policies = await cur.fetchall()
        expected = "(thread_id = NULLIF(current_setting('app.checkpoint_thread_id'::text, true), ''::text))"
        if len(policies) != 3 or any(p['polname'] != 'fm_checkpoint_task' or
                p['using_expr'] != expected or p['check_expr'] != expected for p in policies):
            raise PermissionError("Checkpoint policies do not match the reviewed task boundary.")


@asynccontextmanager
async def postgres_checkpointer(database_url: str, *, repository, task_id: str,
                                 workspace_id: str, user_id: str,
                                 schema: str = 'langgraph_checkpoints'):
    authorize_checkpoint(repository, task_id=task_id, workspace_id=workspace_id, user_id=user_id)
    if not re.fullmatch(r'[a-z][a-z0-9_]*', schema) or schema in {'public', 'pg_catalog'}:
        raise ValueError("A dedicated checkpoint schema is required.")
    async with await AsyncConnection.connect(checkpoint_connection_string(database_url),
            autocommit=True, prepare_threshold=0, row_factory=dict_row) as conn:
        await conn.execute(sql.SQL('SET search_path TO {}, pg_catalog').format(sql.Identifier(schema)))
        await verify_checkpoint_connection(conn, schema)
        thread = checkpoint_thread_id(task_id=task_id, workspace_id=workspace_id)
        lock_id = int.from_bytes(hashlib.sha256(thread.encode()).digest()[:8], 'big', signed=True)
        async with conn.cursor() as cur:
            await cur.execute('SELECT pg_try_advisory_lock(%s) AS acquired', (lock_id,))
            if not (await cur.fetchone())['acquired']:
                raise CheckpointBusyError('This graph task already has an active worker.')
        # Session lock releases on connection close, including cancellation/errors.
        yield AuthorizedPostgresSaver(conn, repository=repository, task_id=task_id,
            workspace_id=workspace_id, user_id=user_id)
