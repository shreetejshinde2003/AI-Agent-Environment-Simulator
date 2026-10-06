"""HR foundation with transaction-time IAM, HR-role checks and immutable history."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from app.models.schemas import HiringRequirementInput, RoleKnowledgeInput, JobDescriptionInput, HRRecord
from app.security.hr_roles import HRHumanAuthorization, HRHumanPermission, HRHumanRole
from app.security.rbac import AuthorizationError, Permission
from app.security.tenant_db_context import tenant_transaction
from app.storage import models as dbm

MODELS = {"requirements": HiringRequirementInput, "role_knowledge": RoleKnowledgeInput,
          "job_descriptions": JobDescriptionInput}
WRITE_PERMISSIONS = {"requirements": HRHumanPermission.HIRING_REQUEST_MANAGE,
                     "role_knowledge": HRHumanPermission.ROLE_KNOWLEDGE_MANAGE,
                     "job_descriptions": HRHumanPermission.JD_DRAFT_EDIT}
TRANSITIONS = {"requirements": {"draft": {"draft", "active", "archived"},
                               "active": {"active", "closed", "archived"},
                               "closed": {"closed", "archived"}, "archived": {"archived"}},
               "role_knowledge": {"active": {"active", "archived"}, "archived": {"archived"}},
               "job_descriptions": {"draft": {"draft", "archived"}, "archived": {"archived"}}}


class HiringError(ValueError):
    def __init__(self, status, code, message):
        self.status_code = status
        self.detail = {"code": code, "message": message}
        super().__init__(message)


class HiringRepository:
    def _hiring_authorization(self, connection, workspace_id, user_id):
        # IAM is the maximum authority. HR grants never establish membership.
        self._recycle_authorization(connection, workspace_id=workspace_id,
                                    user_id=user_id, permission=Permission.WORKSPACE_VIEW)
        workspace = connection.execute(select(dbm.workspaces).where(
            dbm.workspaces.c.id == workspace_id)).mappings().one()
        if workspace["kind"] != "organization":
            raise AuthorizationError("Organization workspace required.")
        rows = connection.execute(select(dbm.organization_human_role_assignments).where(
            dbm.organization_human_role_assignments.c.workspace_id == workspace_id,
            dbm.organization_human_role_assignments.c.user_id == user_id,
            dbm.organization_human_role_assignments.c.active.is_(True))).mappings().all()
        roles = frozenset(HRHumanRole(row["human_role"]) for row in rows
                          if row["human_role"] in {r.value for r in HRHumanRole})
        return HRHumanAuthorization(user_id, workspace_id, roles)

    def _hiring_scope(self, connection, workspace_id, user_id, permission):
        authorization = self._hiring_authorization(connection, workspace_id, user_id)
        if not authorization.allows(permission):
            raise AuthorizationError("HR permission denied.")
        return authorization

    def hiring_capabilities(self, *, workspace_id, user_id):
        with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
            authorization = self._hiring_authorization(connection, workspace_id, user_id)
            return {"view": authorization.allows(HRHumanPermission.HIRING_REQUEST_VIEW),
                    **{kind: authorization.allows(p) for kind, p in WRITE_PERMISSIONS.items()}}

    @staticmethod
    def _hiring_record(connection, kind, record_id, workspace_id, revision=None):
        head, history = dbm.HR_TABLES[kind]
        row = connection.execute(select(head).where(head.c.id == record_id,
            head.c.workspace_id == workspace_id)).mappings().first()
        if row is None:
            raise HiringError(404, "hr_record_unavailable", "Hiring record is unavailable.")
        rev = connection.execute(select(history).where(history.c.record_id == record_id,
            history.c.workspace_id == workspace_id,
            history.c.revision == (revision if revision is not None else row["revision"]))).mappings().first()
        if rev is None:
            raise HiringError(404, "hr_revision_unavailable", "Source revision is unavailable.")
        return HRRecord(id=record_id, workspace_id=workspace_id, revision=rev["revision"],
                        created_by_user_id=row["created_by_user_id"], created_at=row["created_at"],
                        updated_by_user_id=rev["updated_by_user_id"], updated_at=rev["updated_at"],
                        content=MODELS[kind].model_validate(rev["payload"]))

    def list_hiring(self, kind, *, workspace_id, user_id):
        head, _ = dbm.HR_TABLES[kind]
        with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
            self._hiring_scope(connection, workspace_id, user_id, HRHumanPermission.HIRING_REQUEST_VIEW)
            ids = connection.execute(select(head.c.id).where(head.c.workspace_id == workspace_id)
                                     .order_by(head.c.created_at, head.c.id)).scalars().all()
            return [self._hiring_record(connection, kind, rid, workspace_id) for rid in ids]

    def get_hiring(self, kind, record_id, *, workspace_id, user_id, revisions=False):
        with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
            self._hiring_scope(connection, workspace_id, user_id, HRHumanPermission.HIRING_REQUEST_VIEW)
            current = self._hiring_record(connection, kind, record_id, workspace_id)
            if not revisions:
                return current
            _, history = dbm.HR_TABLES[kind]
            versions = connection.execute(select(history.c.revision).where(
                history.c.record_id == record_id, history.c.workspace_id == workspace_id)
                .order_by(history.c.revision)).scalars().all()
            return [self._hiring_record(connection, kind, record_id, workspace_id, v) for v in versions]

    def save_hiring(self, kind, content, *, workspace_id, user_id, record_id=None, expected_revision=None):
        content = MODELS[kind].model_validate(content.model_dump(mode="json"))
        head, history = dbm.HR_TABLES[kind]
        stamp = datetime.now(timezone.utc).isoformat()
        try:
            with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
                self._hiring_scope(connection, workspace_id, user_id, WRITE_PERMISSIONS[kind])
                sources = {}
                if kind == "job_descriptions":
                    for attr, source_kind, column in (("requirement", "requirements", "requirement"),
                                                      ("role_knowledge", "role_knowledge", "knowledge")):
                        source = getattr(content, attr)
                        sources[column + "_id"] = source.id if source else None
                        sources[column + "_revision"] = source.revision if source else None
                        if source:
                            # Explicit scope plus composite FK prevent cross-tenant source references.
                            self._hiring_record(connection, source_kind, source.id, workspace_id, source.revision)
                            latest = self._hiring_record(connection, source_kind, source.id, workspace_id)
                            if record_id is None and latest.content.status in {"archived", "closed"}:
                                raise HiringError(409, "source_inactive", "New drafts require current usable sources.")
                if record_id is None:
                    if content.status != ("active" if kind == "role_knowledge" else "draft"):
                        raise HiringError(409, "invalid_initial_status", "Invalid initial lifecycle state.")
                    record_id = "HR-" + uuid.uuid4().hex
                    revision = 1
                    connection.execute(insert(head).values(id=record_id, workspace_id=workspace_id,
                        revision=revision, status=content.status, created_by_user_id=user_id, created_at=stamp))
                else:
                    previous = self._hiring_record(connection, kind, record_id, workspace_id)
                    if expected_revision != previous.revision:
                        raise HiringError(409, "revision_conflict", "Record changed; reload before saving.")
                    if content.status not in TRANSITIONS[kind][previous.content.status]:
                        raise HiringError(409, "invalid_transition", "Lifecycle transition is not allowed.")
                    if previous.content.status == "archived":
                        raise HiringError(409, "record_archived", "Archived records are read-only.")
                    revision = previous.revision + 1
                    changed = connection.execute(update(head).where(head.c.id == record_id,
                        head.c.workspace_id == workspace_id, head.c.revision == expected_revision)
                        .values(revision=revision, status=content.status)).rowcount
                    if changed != 1:
                        raise HiringError(409, "revision_conflict", "Record changed; reload before saving.")
                connection.execute(insert(history).values(record_id=record_id, revision=revision,
                    workspace_id=workspace_id, updated_by_user_id=user_id, updated_at=stamp,
                    payload=content.model_dump(mode="json"), **sources))
                return self._hiring_record(connection, kind, record_id, workspace_id)
        except IntegrityError as exc:
            raise HiringError(409, "hr_integrity_conflict", "Record revision or source conflicts with saved data.") from exc


    def bind_hr_sources(self, request, *, workspace_id, user_id):
        """Admission and worker checks bind immutable revisions in one transaction."""
        with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
            permission = (HRHumanPermission.JD_REVIEW if request.agent_id == "hr_draft_validation"
                          else HRHumanPermission.JD_DRAFT_EDIT)
            self._hiring_scope(connection, workspace_id, user_id, permission)
            sources = {}
            for name, kind in (("requirement", "requirements"), ("role_knowledge", "role_knowledge"),
                               ("job_description", "job_descriptions")):
                reference = getattr(request, name)
                if reference:
                    sources[name] = self._hiring_record(connection, kind, reference.id, workspace_id, reference.revision)
            if "job_description" in sources:
                draft = sources["job_description"].content
                if draft.requirement != request.requirement or draft.role_knowledge != request.role_knowledge:
                    raise HiringError(409, "source_mismatch", "Validation must use the description's exact saved source revisions.")
            return sources


    def list_hr_runs(self, *, workspace_id, user_id):
        with tenant_transaction(self.engine, workspace_id=workspace_id, user_id=user_id) as connection:
            self._hiring_scope(connection, workspace_id, user_id, HRHumanPermission.HIRING_REQUEST_VIEW)
            rows = connection.execute(select(dbm.simulations).where(
                dbm.simulations.c.workspace_id == workspace_id, dbm.simulations.c.task_type == "hr_agent",
                dbm.simulations.c.deleted_at.is_(None)).order_by(dbm.simulations.c.created_at.desc())).mappings().all()
            return [self._task_from_row(row) for row in rows]
