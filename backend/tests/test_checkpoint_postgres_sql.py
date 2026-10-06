"""Opt-in local Docker RLS proof, entirely rolled back in a random schema.

Administrative connection only creates test-owned objects. Assertions run as
fm_app, with fm_checkpoint owning the tables. No login/credential changes.
This is SQL enforcement proof, not Psycopg saver/reconnect acceptance.
"""
import os
from pathlib import Path
import subprocess
import uuid

import pytest


def test_local_checkpoint_force_rls_and_transaction_context():
    if os.environ.get('RUN_LOCAL_CHECKPOINT_SQL_TESTS') != '1':
        pytest.skip('Opt-in local Docker checkpoint SQL verification not requested')
    schema = 'checkpoint_test_' + uuid.uuid4().hex
    migration = (Path(__file__).parents[1]/'migrations/checkpoint_security.sql').read_text()
    security = migration.replace('langgraph_checkpoints', schema)
    setup = '\n'.join(f'''CREATE TABLE {schema}.{table}
        (LIKE langgraph_checkpoints.{table} INCLUDING ALL);
        ALTER TABLE {schema}.{table} OWNER TO fm_checkpoint;
        GRANT SELECT,INSERT,UPDATE,DELETE ON {schema}.{table} TO fm_app;'''
        for table in ('checkpoints','checkpoint_blobs','checkpoint_writes'))
    inserts = """
        INSERT INTO checkpoints(thread_id,checkpoint_ns,checkpoint_id,checkpoint)
          VALUES ('a','','1','{"v":4}');
        INSERT INTO checkpoint_blobs(thread_id,checkpoint_ns,channel,version,type,blob)
          VALUES ('a','','context','1','json','{}');
        INSERT INTO checkpoint_writes(thread_id,checkpoint_ns,checkpoint_id,task_id,idx,channel,type,blob)
          VALUES ('a','','1','node',0,'context','json','{}');
    """
    script = f'''
    BEGIN;
    DO $$ BEGIN
      IF current_database() <> 'fm_tenant_test' THEN RAISE EXCEPTION 'Wrong database'; END IF;
    END $$;
    CREATE SCHEMA {schema};
    {setup}
    {security}
    GRANT USAGE ON SCHEMA {schema} TO fm_app;
    SET LOCAL ROLE fm_app;
    SET LOCAL search_path TO {schema}, pg_catalog;
    DO $$ BEGIN
      IF (SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user)
        THEN RAISE EXCEPTION 'Bypass runtime'; END IF;
      IF has_schema_privilege(current_user, '{schema}', 'CREATE')
        THEN RAISE EXCEPTION 'Migration privilege'; END IF;
    END $$;
    SELECT set_config('app.checkpoint_thread_id','a',true);
    {inserts}
    DO $$ DECLARE t text; n integer; BEGIN
      FOREACH t IN ARRAY ARRAY['checkpoints','checkpoint_blobs','checkpoint_writes'] LOOP
        EXECUTE format('SELECT count(*) FROM %I',t) INTO n;
        IF n <> 1 THEN RAISE EXCEPTION 'Authorized read failed'; END IF;
      END LOOP;
    END $$;
    SAVEPOINT scope;
    SELECT set_config('app.checkpoint_thread_id','b',true);
    DO $$ DECLARE t text; n integer; BEGIN
      FOREACH t IN ARRAY ARRAY['checkpoints','checkpoint_blobs','checkpoint_writes'] LOOP
        EXECUTE format('SELECT count(*) FROM %I',t) INTO n;
        IF n <> 0 THEN RAISE EXCEPTION 'Cross-thread read leaked'; END IF;
        EXECUTE format('DELETE FROM %I',t);
        GET DIAGNOSTICS n = ROW_COUNT;
        IF n <> 0 THEN RAISE EXCEPTION 'Cross-thread delete leaked'; END IF;
      END LOOP;
      BEGIN
        INSERT INTO checkpoints(thread_id,checkpoint_ns,checkpoint_id,checkpoint)
          VALUES ('a','','2','{{}}');
        RAISE EXCEPTION 'Cross-thread write accepted';
      EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    END $$;
    ROLLBACK TO scope;
    DO $$ BEGIN
      IF current_setting('app.checkpoint_thread_id') <> 'a'
        THEN RAISE EXCEPTION 'Rollback leaked context'; END IF;
    END $$;
    SELECT set_config('app.checkpoint_thread_id','',true);
    DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM checkpoints) THEN RAISE EXCEPTION 'Missing context leaked'; END IF;
    END $$;
    ROLLBACK;
    DO $$ BEGIN
      IF NULLIF(current_setting('app.checkpoint_thread_id',true),'') IS NOT NULL
        THEN RAISE EXCEPTION 'Transaction setting leaked'; END IF;
      IF to_regnamespace('{schema}') IS NOT NULL THEN RAISE EXCEPTION 'Test schema leaked'; END IF;
    END $$;
    '''
    result = subprocess.run(['docker','exec','-i','fm-tenant-postgres','psql',
        '-v','ON_ERROR_STOP=1','-U','postgres','-d','fm_tenant_test'],
        input=script, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
