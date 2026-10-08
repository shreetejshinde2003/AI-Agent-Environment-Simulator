"""Opt-in atomic checkpoint/evidence deletion using only isolated local schemas."""
import os
import re
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError

from app.core.config import settings
from app.agents.checkpointing import checkpoint_thread_id
from app.security.tenant_db_context import tenant_transaction
from app.storage.database import RecycleBinError
from test_postgres_data_plane_integration import pg_repo, seed


def local_sql(script):
    result = subprocess.run(['docker', 'exec', '-i', 'fm-tenant-postgres', 'psql', '-U', 'postgres',
        '-d', 'fm_tenant_test', '-v', 'ON_ERROR_STOP=1', '-At'], input=script, text=True,
        capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def bridge(pg_repo, monkeypatch):
    if os.environ.get('RUN_LOCAL_CHECKPOINT_SQL_TESTS') != '1':
        pytest.skip('Local checkpoint bridge SQL acceptance requires opt-in')
    with pg_repo.engine.connect() as connection:
        schema, actor = connection.execute(text('SELECT current_schema(),current_user')).one()
    assert re.fullmatch(r'tenant_test_[a-f0-9]+', schema)
    checkpoint = 'purge_cp_' + uuid.uuid4().hex
    role = 'purge_owner_' + uuid.uuid4().hex
    security = (Path(__file__).parents[1] / 'migrations/checkpoint_security.sql').read_text().replace('langgraph_checkpoints', checkpoint)
    migration = (Path(__file__).parents[1] / 'migrations/checkpoint_purge.sql').read_text().replace('public.', schema+'.').replace('SCHEMA public,', 'SCHEMA '+schema+',').replace('langgraph_checkpoints', checkpoint).replace('fm_checkpoint_purge', role).replace('TO fm_app;', 'TO '+actor+';')
    setup = f'CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS; CREATE SCHEMA {checkpoint};\n'
    for table in ('checkpoints', 'checkpoint_blobs', 'checkpoint_writes'):
        setup += f'CREATE TABLE {checkpoint}.{table} (LIKE langgraph_checkpoints.{table} INCLUDING ALL); ALTER TABLE {checkpoint}.{table} OWNER TO fm_checkpoint;\n'
    local_sql(setup + security + migration)
    monkeypatch.setattr(settings, 'CHECKPOINT_DATABASE_URL', pg_repo.url)
    try:
        yield pg_repo, checkpoint
    finally:
        local_sql(f'DROP FUNCTION {schema}.fm_purge_task_checkpoints(text); DROP SCHEMA {checkpoint} CASCADE; DROP OWNED BY {role}; DROP ROLE {role};')


def checkpoint_seed(repo, schema, task):
    thread = checkpoint_thread_id(task_id=task.id, workspace_id=task.workspace_id)
    local_sql(f"INSERT INTO {schema}.checkpoints(thread_id,checkpoint_ns,checkpoint_id,checkpoint) VALUES ('{thread}','','1','{{\"v\":4}}');\n"
              f"INSERT INTO {schema}.checkpoint_blobs(thread_id,checkpoint_ns,channel,version,type,blob) VALUES ('{thread}','','context','1','json','{{}}');\n"
              f"INSERT INTO {schema}.checkpoint_writes(thread_id,checkpoint_ns,checkpoint_id,task_id,idx,channel,type,blob) VALUES ('{thread}','','1','node',0,'context','json','{{}}');")


def count(schema):
    return local_sql(f'SELECT (SELECT count(*) FROM {schema}.checkpoints)+(SELECT count(*) FROM {schema}.checkpoint_blobs)+(SELECT count(*) FROM {schema}.checkpoint_writes);')


def test_atomic_purge_removes_only_authorized_thread(bridge):
    repo, schema = bridge
    a = seed(repo, 'T-purge-a', 'USR-a'); b = seed(repo, 'T-purge-b', 'USR-b')
    checkpoint_seed(repo, schema, a); checkpoint_seed(repo, schema, b)
    scope = dict(workspace_id=a.workspace_id, user_id='USR-a')
    repo.recycle_simulation(a.id, **scope)
    with tenant_transaction(repo.engine, **scope) as connection:
        with pytest.raises(DBAPIError):
            with connection.begin_nested():
                connection.execute(text('SELECT fm_purge_task_checkpoints(:id)'), {'id': b.id})
    repo.recycle_simulation(a.id, **scope, action='purge', confirmed=True)
    assert count(schema) == '3'
    assert repo.get_for_tenant(b.id, workspace_id=b.workspace_id, user_id='USR-b') is not None
    with repo.engine.connect() as connection:
        assert not connection.execute(text("SELECT has_schema_privilege(current_user,:schema,'USAGE')"), {'schema': schema}).scalar()


def test_checkpoint_cleanup_rolls_back_with_parent_failure(bridge):
    repo, schema = bridge
    task = seed(repo, 'T-atomic', 'USR-a'); checkpoint_seed(repo, schema, task)
    scope = dict(workspace_id=task.workspace_id, user_id='USR-a')
    repo.recycle_simulation(task.id, **scope)
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith('DELETE FROM simulations '):
            raise RuntimeError('Injected parent-delete failure')
    event.listen(repo.engine, 'before_cursor_execute', fail)
    try:
        with pytest.raises(RuntimeError, match='Injected'):
            repo.recycle_simulation(task.id, **scope, action='purge', confirmed=True)
    finally:
        event.remove(repo.engine, 'before_cursor_execute', fail)
    assert count(schema) == '3'
    assert repo.list_recycled_simulations(**scope)[0]['id'] == task.id
    repo.recycle_simulation(task.id, **scope, action='purge', confirmed=True)
    assert count(schema) == '0'


def test_different_checkpoint_database_fails_closed(bridge, monkeypatch):
    repo, schema = bridge
    task = seed(repo, 'T-different-db', 'USR-a')
    checkpoint_seed(repo, schema, task)
    scope = dict(workspace_id=task.workspace_id, user_id='USR-a')
    repo.recycle_simulation(task.id, **scope)
    monkeypatch.setattr(settings, 'CHECKPOINT_DATABASE_URL', 'postgresql://localhost/other_database')
    with pytest.raises(RecycleBinError, match='same database'):
        repo.recycle_simulation(task.id, **scope, action='purge', confirmed=True)
    assert count(schema) == '3'
    assert repo.list_recycled_simulations(**scope)[0]['id'] == task.id


def test_checkpoint_bridge_denies_unscoped_and_disabled_actor(bridge):
    repo, schema = bridge
    task = seed(repo, 'T-denied', 'USR-a'); checkpoint_seed(repo, schema, task)
    scope = dict(workspace_id=task.workspace_id, user_id='USR-a')
    repo.recycle_simulation(task.id, **scope)
    with repo.engine.begin() as connection:
        with pytest.raises(DBAPIError):
            with connection.begin_nested():
                connection.execute(text('SELECT fm_purge_task_checkpoints(:id)'), {'id': task.id})
    with repo.engine.begin() as connection:
        connection.execute(text("UPDATE users SET active=false WHERE id='USR-a'"))
    with tenant_transaction(repo.engine, **scope) as connection:
        with pytest.raises(DBAPIError):
            with connection.begin_nested():
                connection.execute(text('SELECT fm_purge_task_checkpoints(:id)'), {'id': task.id})
    assert count(schema) == '3'
