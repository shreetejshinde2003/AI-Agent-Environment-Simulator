-- Operator-installed bridge for atomic run/checkpoint purge in the SAME database.
-- Install in the application schema (public here); replace schema names explicitly
-- for isolated acceptance. No runtime login credentials or schema privileges added.
-- fm_checkpoint_purge is a dedicated NOLOGIN, NOSUPERUSER, NOBYPASSRLS role.
-- Provision that role separately, then run as an authorized migration administrator.
GRANT USAGE ON SCHEMA public, langgraph_checkpoints TO fm_checkpoint_purge;
GRANT SELECT (id, active) ON public.users TO fm_checkpoint_purge;
GRANT SELECT ON public.simulations, public.workspaces, public.organization_memberships,
    public.organization_human_role_assignments TO fm_checkpoint_purge;
GRANT SELECT, DELETE ON langgraph_checkpoints.checkpoints,
    langgraph_checkpoints.checkpoint_blobs, langgraph_checkpoints.checkpoint_writes TO fm_checkpoint_purge;
CREATE OR REPLACE FUNCTION public.fm_purge_task_checkpoints(simulation_id text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
    tenant text := NULLIF(current_setting('app.current_workspace_id', true), '');
    actor text := NULLIF(current_setting('app.current_user_id', true), '');
    thread text;
BEGIN
    IF tenant IS NULL OR actor IS NULL
       OR NOT EXISTS (SELECT 1 FROM public.users u WHERE u.id = actor AND u.active)
       OR NOT EXISTS (
        SELECT 1 FROM public.simulations s JOIN public.workspaces w ON w.id = s.workspace_id
        WHERE s.id = simulation_id AND s.workspace_id = tenant AND s.deleted_at IS NOT NULL
          AND s.status IN ('completed', 'failed') AND w.active AND (
            (w.kind = 'personal' AND w.personal_owner_user_id = actor) OR
            (w.kind = 'organization' AND EXISTS (SELECT 1 FROM public.organization_memberships m
                WHERE m.workspace_id = tenant AND m.user_id = actor AND m.active AND m.membership_role = 'owner')))
    ) THEN
        RAISE EXCEPTION 'Purge authorization denied' USING ERRCODE = '42501';
    END IF;
    -- Server-generated identifiers are ASCII; fail closed for legacy identifiers
    -- whose Python JSON escaping would differ from PostgreSQL's JSON encoding.
    IF octet_length(tenant) <> length(tenant) OR octet_length(simulation_id) <> length(simulation_id) THEN
        RAISE EXCEPTION 'Unsupported checkpoint identity' USING ERRCODE = '55006';
    END IF;
    thread := 'fm-v1-' || encode(sha256(convert_to('[' || to_json(tenant)::text || ',' || to_json(simulation_id)::text || ']', 'UTF8')), 'hex');
    IF NOT pg_try_advisory_xact_lock(('x' || substr(encode(sha256(convert_to(thread, 'UTF8')), 'hex'), 1, 16))::bit(64)::bigint) THEN
        RAISE EXCEPTION 'Checkpoint worker still active' USING ERRCODE = '55006';
    END IF;
    PERFORM set_config('app.checkpoint_thread_id', thread, true);
    DELETE FROM langgraph_checkpoints.checkpoint_writes WHERE thread_id = thread;
    DELETE FROM langgraph_checkpoints.checkpoint_blobs WHERE thread_id = thread;
    DELETE FROM langgraph_checkpoints.checkpoints WHERE thread_id = thread;
    PERFORM set_config('app.checkpoint_thread_id', '', true);
END;
$$;
ALTER FUNCTION public.fm_purge_task_checkpoints(text) OWNER TO fm_checkpoint_purge;
REVOKE ALL ON FUNCTION public.fm_purge_task_checkpoints(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fm_purge_task_checkpoints(text) TO fm_app;
