"""Append-only human review workflow; no AI or publication authority."""
import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import insert, select, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.models.schemas import HRReviewRecord, HRReviewEvent
from app.security.hr_roles import HRHumanPermission
from app.security.tenant_db_context import tenant_transaction
from app.storage import models as dbm
from app.storage.hiring import HiringError

TRANSITIONS = {
    'pending_review': {'recommend': 'reviewed', 'request_changes': 'changes_requested', 'reject': 'rejected'},
    'reviewed': {'approve': 'approved', 'request_changes': 'changes_requested', 'reject': 'rejected'},
}
DECISION_PERMISSIONS = {
    'recommend': HRHumanPermission.JD_REVIEW,
    'request_changes': HRHumanPermission.JD_REQUEST_REVISION,
    'reject': HRHumanPermission.JD_REJECT,
    'approve': HRHumanPermission.JD_APPROVE,
}


def lock_review_document(connection, record_id):
    # Shared with authoritative JD editing. No reviewer needs draft UPDATE grants.
    if connection.dialect.name == 'sqlite':
        connection.exec_driver_sql('BEGIN IMMEDIATE')
    elif record_id:
        key = int.from_bytes(hashlib.md5(record_id.encode(), usedforsecurity=False).digest()[:8], 'big', signed=True)
        connection.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': key})


def install_review_guards(connection):
    """Database checks protect append order and stale decisions even via direct SQL."""
    submission_check = """NOT EXISTS (SELECT 1 FROM hr_job_descriptions j WHERE j.id = NEW.jd_id
        AND j.workspace_id = NEW.workspace_id AND j.revision = NEW.jd_revision AND j.status = 'draft')"""
    event_check = """NEW.version <> COALESCE((SELECT MAX(e.version) FROM hr_review_events e
        WHERE e.submission_id = NEW.submission_id), 0) + 1
        OR (NEW.version > 1 AND NEW.from_status <> (SELECT e.to_status FROM hr_review_events e
            WHERE e.submission_id = NEW.submission_id ORDER BY e.version DESC LIMIT 1))
        OR NOT EXISTS (SELECT 1 FROM hr_review_submissions s JOIN hr_job_descriptions j
            ON j.id = s.jd_id AND j.workspace_id = s.workspace_id WHERE s.id = NEW.submission_id
            AND s.workspace_id = NEW.workspace_id AND j.revision = s.jd_revision AND j.status = 'draft')"""
    for table, condition in (('hr_review_submissions', submission_check), ('hr_review_events', event_check)):
        if connection.dialect.name == 'sqlite':
            connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS validate_{table} BEFORE INSERT ON {table} "
                f"WHEN {condition} BEGIN SELECT RAISE(ABORT, 'Review transition conflict'); END")
        else:
            lock = ("PERFORM pg_advisory_xact_lock(('x' || substr(md5(NEW.jd_id),1,16))::bit(64)::bigint);"
                    if table == 'hr_review_submissions' else
                    "PERFORM pg_advisory_xact_lock(('x' || substr(md5(s.jd_id),1,16))::bit(64)::bigint) FROM hr_review_submissions s WHERE s.id = NEW.submission_id;")
            # Trigger serialization supplements application locks for direct SQL callers.
            connection.exec_driver_sql(f"CREATE OR REPLACE FUNCTION validate_{table}() RETURNS trigger LANGUAGE plpgsql AS $$ "
                f"BEGIN {lock} IF {condition} THEN RAISE EXCEPTION 'Review transition conflict' USING ERRCODE='23514'; "
                "END IF; RETURN NEW; END $$")
            connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS validate_{table} ON {table}")
            connection.exec_driver_sql(f"CREATE TRIGGER validate_{table} BEFORE INSERT ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION validate_{table}()")


class HRReviewRepository:
    def review_capabilities(self, *, workspace_id, user_id):
        with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
            auth = self._hiring_authorization(connection, workspace_id, user_id)
            return {'submit': auth.allows(HRHumanPermission.JD_DRAFT_EDIT),
                    **{key: auth.allows(value) for key, value in DECISION_PERMISSIONS.items()}}

    def _review_record(self, connection, submission_id, workspace_id):
        row = connection.execute(select(dbm.hr_review_submissions).where(
            dbm.hr_review_submissions.c.id == submission_id,
            dbm.hr_review_submissions.c.workspace_id == workspace_id)).mappings().first()
        if row is None:
            raise HiringError(404, 'review_unavailable', 'Review request is unavailable.')
        events = connection.execute(select(dbm.hr_review_events).where(
            dbm.hr_review_events.c.submission_id == submission_id,
            dbm.hr_review_events.c.workspace_id == workspace_id).order_by(dbm.hr_review_events.c.version)).mappings().all()
        jd = self._hiring_record(connection, 'job_descriptions', row['jd_id'], workspace_id, row['jd_revision'])
        head = self._hiring_record(connection, 'job_descriptions', row['jd_id'], workspace_id)
        return HRReviewRecord(id=row['id'], workspace_id=workspace_id,
            requested_by_user_id=row['requested_by_user_id'], submitted_at=row['submitted_at'],
            job_description=jd, requirement=self._hiring_record(connection, 'requirements', jd.content.requirement.id,
                workspace_id, jd.content.requirement.revision),
            role_knowledge=self._hiring_record(connection, 'role_knowledge', jd.content.role_knowledge.id,
                workspace_id, jd.content.role_knowledge.revision) if jd.content.role_knowledge else None,
            ai_run_ids=row['ai_run_ids'], status=events[-1]['to_status'], version=events[-1]['version'],
            stale=head.revision != jd.revision or head.content.status != 'draft',
            history=[HRReviewEvent.model_validate(dict(event)) for event in events])

    def get_review(self, submission_id, *, workspace_id, user_id):
        with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
            self._hiring_scope(connection, workspace_id, user_id, HRHumanPermission.HIRING_REQUEST_VIEW)
            return self._review_record(connection, submission_id, workspace_id)

    def list_reviews(self, *, workspace_id, user_id):
        with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
            self._hiring_scope(connection, workspace_id, user_id, HRHumanPermission.HIRING_REQUEST_VIEW)
            ids = connection.execute(select(dbm.hr_review_submissions.c.id).where(
                dbm.hr_review_submissions.c.workspace_id == workspace_id).order_by(
                dbm.hr_review_submissions.c.submitted_at.desc(), dbm.hr_review_submissions.c.id)).scalars().all()
            return [self._review_record(connection, rid, workspace_id) for rid in ids]

    def submit_review(self, payload, *, workspace_id, user_id):
        try:
            with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
                lock_review_document(connection, payload.job_description.id)
                self._hiring_scope(connection, workspace_id, user_id, HRHumanPermission.JD_DRAFT_EDIT)
                jd = self._hiring_record(connection, 'job_descriptions', payload.job_description.id, workspace_id)
                if jd.revision != payload.job_description.revision or jd.content.status != 'draft':
                    raise HiringError(409, 'stale_submission', 'Submit the current editable JD revision.')
                if len(set(payload.ai_run_ids)) != len(payload.ai_run_ids):
                    raise HiringError(422, 'duplicate_ai_reference', 'AI run references must be unique.')
                for run_id in payload.ai_run_ids:
                    row = connection.execute(select(dbm.simulations).where(dbm.simulations.c.id == run_id,
                        dbm.simulations.c.workspace_id == workspace_id, dbm.simulations.c.task_type == 'hr_agent',
                        dbm.simulations.c.deleted_at.is_(None))).mappings().first()
                    if row is None:
                        raise HiringError(404, 'ai_run_unavailable', 'AI run is unavailable.')
                    task = self._task_from_row(row)
                    request = task.hr_execution.request
                    if (task.status.value != 'completed' or request.requirement != jd.content.requirement
                            or request.role_knowledge != jd.content.role_knowledge
                            or (request.job_description is not None and request.job_description != payload.job_description)):
                        raise HiringError(409, 'ai_source_mismatch', 'Associate only completed AI proposals with matching pinned sources.')
                sid = 'HRR-' + uuid.uuid4().hex
                stamp = datetime.now(timezone.utc).isoformat()
                connection.execute(insert(dbm.hr_review_submissions).values(id=sid, workspace_id=workspace_id,
                    jd_id=jd.id, jd_revision=jd.revision, requested_by_user_id=user_id, submitted_at=stamp,
                    ai_run_ids=payload.ai_run_ids))
                self._append_review_event(connection, sid, workspace_id, user_id, stamp, 1, 'submit', 'draft', 'pending_review', '')
                return self._review_record(connection, sid, workspace_id)
        except (IntegrityError, OperationalError) as exc:
            if isinstance(exc, OperationalError) and not (
                    getattr(exc.orig, 'sqlstate', getattr(exc.orig, 'pgcode', None)) in {'40001', '40P01'}
                    or (self.engine.dialect.name == 'sqlite' and 'locked' in str(exc.orig).lower())):
                raise
            raise HiringError(409, 'review_conflict', 'Revision already submitted or changed; reload before submitting.') from exc

    @staticmethod
    def _append_review_event(connection, sid, workspace_id, user_id, stamp, version, action, previous, status, notes):
        connection.execute(insert(dbm.hr_review_events).values(id='HRE-' + uuid.uuid4().hex,
            submission_id=sid, workspace_id=workspace_id, version=version, action=action,
            actor_user_id=user_id, occurred_at=stamp, from_status=previous, to_status=status, notes=notes))

    def decide_review(self, submission_id, payload, *, approval=False, workspace_id, user_id):
        try:
            with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
                if connection.dialect.name == 'sqlite':
                    lock_review_document(connection, None)
                self._hiring_scope(connection, workspace_id, user_id, DECISION_PERMISSIONS[payload.decision])
                record = self._review_record(connection, submission_id, workspace_id)
                if connection.dialect.name != 'sqlite':
                    lock_review_document(connection, record.job_description.id)
                    record = self._review_record(connection, submission_id, workspace_id)
                    self._hiring_scope(connection, workspace_id, user_id, DECISION_PERMISSIONS[payload.decision])
                if approval:
                    self._hiring_scope(connection, workspace_id, user_id, HRHumanPermission.JD_APPROVE)
                if (record.stale or payload.expected_version != record.version
                        or record.status != ('reviewed' if approval else 'pending_review')
                        or payload.decision not in TRANSITIONS.get(record.status, {})):
                    raise HiringError(409, 'review_conflict', 'Request changed or is ineligible; reload before deciding.')
                status = TRANSITIONS[record.status][payload.decision]
                self._append_review_event(connection, submission_id, workspace_id, user_id,
                    datetime.now(timezone.utc).isoformat(), record.version + 1,
                    payload.decision, record.status, status, payload.notes)
                return self._review_record(connection, submission_id, workspace_id)
        except (IntegrityError, OperationalError) as exc:
            if isinstance(exc, OperationalError) and not (
                    getattr(exc.orig, 'sqlstate', getattr(exc.orig, 'pgcode', None)) in {'40001', '40P01'}
                    or (self.engine.dialect.name == 'sqlite' and 'locked' in str(exc.orig).lower())):
                raise
            raise HiringError(409, 'review_conflict', 'Concurrent decision or revision change; reload before deciding.') from exc
