-- Run separately as the checkpoint migration owner after AsyncPostgresSaver.setup().
-- Runtime LOGIN must be provisioned privately by the operator; never grant it
-- membership in fm_checkpoint (table owner) or BYPASSRLS. No credentials here.
ALTER TABLE langgraph_checkpoints.checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE langgraph_checkpoints.checkpoints FORCE ROW LEVEL SECURITY;
ALTER TABLE langgraph_checkpoints.checkpoint_blobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE langgraph_checkpoints.checkpoint_blobs FORCE ROW LEVEL SECURITY;
ALTER TABLE langgraph_checkpoints.checkpoint_writes ENABLE ROW LEVEL SECURITY;
ALTER TABLE langgraph_checkpoints.checkpoint_writes FORCE ROW LEVEL SECURITY;
CREATE POLICY fm_checkpoint_task ON langgraph_checkpoints.checkpoints
  USING (thread_id = NULLIF(current_setting('app.checkpoint_thread_id', true), ''))
  WITH CHECK (thread_id = NULLIF(current_setting('app.checkpoint_thread_id', true), ''));
CREATE POLICY fm_checkpoint_task ON langgraph_checkpoints.checkpoint_blobs
  USING (thread_id = NULLIF(current_setting('app.checkpoint_thread_id', true), ''))
  WITH CHECK (thread_id = NULLIF(current_setting('app.checkpoint_thread_id', true), ''));
CREATE POLICY fm_checkpoint_task ON langgraph_checkpoints.checkpoint_writes
  USING (thread_id = NULLIF(current_setting('app.checkpoint_thread_id', true), ''))
  WITH CHECK (thread_id = NULLIF(current_setting('app.checkpoint_thread_id', true), ''));
-- Grant only USAGE on schema and SELECT/INSERT/UPDATE/DELETE on these three
-- tables to the separate runtime login. No CREATE, owner membership, or
-- checkpoint_migrations access. fm_app keeps no checkpoint schema privileges.
