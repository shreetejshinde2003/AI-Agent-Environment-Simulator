"""Version 14 operational tables; benchmark records never enter this schema."""

from sqlalchemy import (JSON, Boolean, CheckConstraint, Column, Float, ForeignKey,
                        Index, Integer, MetaData, String, Table, Text, UniqueConstraint, ForeignKeyConstraint)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()
json_type = JSON().with_variant(JSONB, "postgresql")

schema_version = Table("schema_version", metadata,
    Column("version", Integer, primary_key=True), Column("applied_at", String(40), nullable=False))

# ---------------------------------------------------------------------------
# Authentication identity.
#
# Google authenticates the person. These tables store only the application's
# local identity and revocable application sessions. No Google password and
# no Google OAuth access/refresh token belongs here.
# ---------------------------------------------------------------------------
users = Table("users", metadata,
    Column("id", String(80), primary_key=True),
    Column("google_sub", String(255), nullable=False, unique=True),
    Column("email", String(320), nullable=False),
    Column("display_name", String(255), nullable=False),
    Column("profile_picture", Text),
    Column("email_verified", Boolean, nullable=False, default=False),
    Column("active", Boolean, nullable=False, default=True),
    Column("created_at", String(40), nullable=False),
    Column("last_login_at", String(40)))
Index("ix_users_email", users.c.email)

auth_sessions = Table("auth_sessions", metadata,
    Column("id", String(80), primary_key=True),
    Column("user_id", String(80),
           ForeignKey("users.id", ondelete="CASCADE"),
           nullable=False),
    # Only a SHA-256 digest of the opaque browser session credential is stored.
    Column("token_digest", String(64), nullable=False, unique=True),
    Column("created_at", String(40), nullable=False),
    Column("expires_at", String(40), nullable=False),
    Column("revoked_at", String(40)))
Index("ix_auth_sessions_user", auth_sessions.c.user_id)
Index("ix_auth_sessions_expires", auth_sessions.c.expires_at)

# ---------------------------------------------------------------------------
# Workspace / tenancy foundation.
#
# A workspace is the common ownership boundary used by both:
#   - one private Personal Workspace for one user
#   - a shared Organization that can later have multiple members
#
# Memberships are intentionally added in Phase 4.2.2. This phase establishes
# only the stable workspace identity that later simulations and HR records can
# reference.
# ---------------------------------------------------------------------------
workspaces = Table(
    "workspaces",
    metadata,
    Column("id", String(80), primary_key=True),
    Column("kind", String(20), nullable=False),
    Column("name", String(255), nullable=False),

    # Set only for Personal Workspaces. UNIQUE guarantees that one user cannot
    # accidentally receive multiple Personal Workspaces. Multiple NULL values
    # remain valid for Organization rows.
    Column(
        "personal_owner_user_id",
        String(80),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    ),

    # The creator is retained independently from later organization roles.
    Column(
        "created_by_user_id",
        String(80),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    ),

    Column("invite_history", json_type, nullable=True),

    # Organization join codes will be generated in Phase 4.2.5/4.2.6.
    # Only a digest belongs in persistent storage, never the shareable code.
    Column(
        "join_code_digest",
        String(64),
        nullable=True,
        unique=True,
    ),

    Column("active", Boolean, nullable=False, default=True),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),

    CheckConstraint(
        "kind IN ('personal', 'organization')",
        name="ck_workspaces_kind",
    ),
    CheckConstraint(
        "kind != 'personal' OR personal_owner_user_id IS NOT NULL",
        name="ck_personal_workspace_has_owner",
    ),
    CheckConstraint(
        "kind != 'organization' OR personal_owner_user_id IS NULL",
        name="ck_organization_has_no_personal_owner",
    ),
)

Index(
    "ix_workspaces_kind_active",
    workspaces.c.kind,
    workspaces.c.active,
)

Index(
    "ix_workspaces_created_by",
    workspaces.c.created_by_user_id,
)

# ---------------------------------------------------------------------------
# Organization membership.
#
# Personal Workspaces do not use this table. They remain private and are
# owned directly through workspaces.personal_owner_user_id.
#
# These roles are tenancy/IAM roles. HR-domain human responsibilities are
# stored separately in organization_human_role_assignments.
# ---------------------------------------------------------------------------
organization_memberships = Table(
    "organization_memberships",
    metadata,

    Column(
        "workspace_id",
        String(80),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    ),

    Column(
        "user_id",
        String(80),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),

    Column(
        "membership_role",
        String(20),
        nullable=False,
    ),

    Column(
        "active",
        Boolean,
        nullable=False,
        default=True,
    ),

    Column(
        "joined_at",
        String(40),
        nullable=False,
    ),

    Column(
        "added_by_user_id",
        String(80),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    ),

    CheckConstraint(
        "membership_role IN ('owner', 'admin', 'member')",
        name="ck_organization_membership_role",
    ),
)

Index(
    "ix_org_memberships_user_active",
    organization_memberships.c.user_id,
    organization_memberships.c.active,
)

Index(
    "ix_org_memberships_workspace_active",
    organization_memberships.c.workspace_id,
    organization_memberships.c.active,
)

# ---------------------------------------------------------------------------
# HR-domain human role assignments.
#
# These are deliberately independent from tenancy roles (owner/admin/member).
# A single active Organization member may hold multiple HR roles concurrently.
# Personal Workspaces never use this table.
# ---------------------------------------------------------------------------
organization_human_role_assignments = Table(
    "organization_human_role_assignments",
    metadata,
    Column(
        "workspace_id",
        String(80),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id",
        String(80),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("human_role", String(40), primary_key=True),
    Column("active", Boolean, nullable=False, default=True),
    Column("assigned_at", String(40), nullable=False),
    Column(
        "assigned_by_user_id",
        String(80),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    CheckConstraint(
        "human_role IN ('hr_recruiter', 'hr_reviewer', 'hr_approver')",
        name="ck_organization_human_role",
    ),
)

Index(
    "ix_org_human_roles_user_active",
    organization_human_role_assignments.c.user_id,
    organization_human_role_assignments.c.active,
)
Index(
    "ix_org_human_roles_workspace_active",
    organization_human_role_assignments.c.workspace_id,
    organization_human_role_assignments.c.active,
)

dataset_registry = Table("dataset_registry", metadata,
    Column("dataset_id", String(80), primary_key=True), Column("name", String(120), nullable=False),
    Column("family", String(40), nullable=False), Column("size_variant", String(20), nullable=False),
    Column("source_filename", String(120), nullable=False), Column("record_count", Integer, nullable=False),
    Column("schema_columns", json_type, nullable=False), Column("checksum", String(64), nullable=False),
    Column("active", Boolean, nullable=False), Column("imported_at", String(40), nullable=False),
    Column("quality", json_type, nullable=False))
simulations = Table("simulations", metadata,
    Column("id", String(80), primary_key=True), Column("owner_id", String(80)),
    Column("workspace_id", String(80), ForeignKey("workspaces.id", ondelete="RESTRICT")),
    Column("dataset_id", String(80), ForeignKey("dataset_registry.dataset_id", ondelete="SET NULL")),
    Column("dataset_checksum", String(64)), Column("status", String(30), nullable=False),
    Column("execution_mode", String(30), nullable=False), Column("task_type", String(80)),
    Column("created_at", String(40), nullable=False), Column("started_at", String(40)),
    Column("completed_at", String(40)),
    Column("deleted_at", String(40)), Column("deleted_by_user_id", String(80)),
    Column("restored_at", String(40)), Column("restored_by_user_id", String(80)),
    Column("payload", json_type, nullable=False))
Index("ix_simulations_status_created", simulations.c.status, simulations.c.created_at)
Index("ix_simulations_workspace_created", simulations.c.workspace_id, simulations.c.created_at)
Index("ix_simulations_dataset", simulations.c.dataset_id)
Index("ix_simulations_workspace_deleted", simulations.c.workspace_id, simulations.c.deleted_at)
tasks = Table("tasks", metadata,
    Column("id", String(80), primary_key=True),
    Column("simulation_id", String(80), ForeignKey("simulations.id", ondelete="CASCADE"), unique=True, nullable=False),
    Column("directive", Text, nullable=False), Column("assigned_agent_id", String(80), nullable=False),
    Column("priority", String(20), nullable=False), Column("status", String(30), nullable=False),
    Column("output", Text), Column("error", Text))
agent_executions = Table("agent_executions", metadata,
    Column("simulation_id", String(80), ForeignKey("simulations.id", ondelete="CASCADE"), primary_key=True),
    Column("position", Integer, primary_key=True), Column("agent_id", String(80), nullable=False),
    Column("output_key", String(80), nullable=False), Column("status", String(30), nullable=False),
    Column("started_at", String(40)), Column("completed_at", String(40)),
    Column("duration_seconds", Float), Column("model", String(120)),
    Column("input_tokens", Integer), Column("output_tokens", Integer), Column("total_tokens", Integer),
    Column("output", Text), Column("error", Text))
Index("ix_agent_executions_agent", agent_executions.c.agent_id)
agent_messages = Table("agent_messages", metadata,
    Column("id", String(80), primary_key=True),
    Column("simulation_id", String(80), ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False),
    Column("from_agent_id", String(80), nullable=False), Column("to_agent_id", String(80), nullable=False),
    Column("kind", String(30), nullable=False), Column("output_key", String(80)),
    Column("timestamp", String(40), nullable=False), Column("content", Text, nullable=False))
Index("ix_agent_messages_sim_time", agent_messages.c.simulation_id, agent_messages.c.timestamp)
activity_events = Table("activity_events", metadata,
    Column("id", String(80), primary_key=True),
    Column("simulation_id", String(80), ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False),
    Column("agent_id", String(80), nullable=False), Column("timestamp", String(40), nullable=False),
    Column("text", Text, nullable=False))
run_events = Table("run_events", metadata,
    Column("id", String(80), primary_key=True),
    Column("simulation_id", String(80), ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False),
    Column("type", String(60), nullable=False), Column("agent_id", String(80)),
    Column("timestamp", String(40), nullable=False), Column("text", Text, nullable=False))
Index("ix_run_events_sim_time", run_events.c.simulation_id, run_events.c.timestamp)
simulation_metrics = Table("simulation_metrics", metadata,
    Column("simulation_id", String(80), ForeignKey("simulations.id", ondelete="CASCADE"), primary_key=True),
    Column("elapsed_seconds", Float), Column("total_tokens", Integer),
    Column("measured_stages", Integer, nullable=False))
uploads = Table("uploads", metadata,
    Column("id", String(80), primary_key=True),
    Column("workspace_id", String(80),
           ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=True),
    Column("created_by_user_id", String(80),
           ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
    Column("filename", String(255), nullable=False),
    Column("format", String(20), nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("payload", json_type, nullable=False))

Index("ix_uploads_workspace_created", uploads.c.workspace_id, uploads.c.created_at)
Index("ix_uploads_created_by", uploads.c.created_by_user_id)
simulation_uploads = Table("simulation_uploads", metadata,
    Column("simulation_id", String(80), ForeignKey("simulations.id", ondelete="CASCADE"), primary_key=True),
    Column("upload_id", String(80), ForeignKey("uploads.id", ondelete="RESTRICT"), primary_key=True))
agent_roster = Table("agent_roster", metadata,
    Column("id", String(80), primary_key=True), Column("payload", json_type, nullable=False))


# V11: immutable configuration revisions are retained when a definition is archived.
custom_agents = Table("custom_agents", metadata,
    Column("id", String(80), primary_key=True),
    Column("workspace_id", String(80), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False),
    Column("name_key", String(240), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("active", Boolean, nullable=False),
    Column("created_by_user_id", String(80), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
    Column("created_at", String(40), nullable=False),
    UniqueConstraint("workspace_id", "name_key", name="uq_custom_agent_name"),
    UniqueConstraint("id", "workspace_id", name="uq_custom_agent_tenant"),
    CheckConstraint("revision >= 1", name="ck_custom_agent_revision"))
custom_agent_revisions = Table("custom_agent_revisions", metadata,
    Column("agent_id", String(80), primary_key=True),
    Column("revision", Integer, primary_key=True),
    Column("workspace_id", String(80), nullable=False),
    Column("updated_by_user_id", String(80), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
    Column("updated_at", String(40), nullable=False),
    Column("config_hash", String(64), nullable=False),
    Column("resolved_model", String(160), nullable=False),
    Column("payload", json_type, nullable=False),
    ForeignKeyConstraint(["agent_id", "workspace_id"], ["custom_agents.id", "custom_agents.workspace_id"], ondelete="RESTRICT"),
    CheckConstraint("revision >= 1", name="ck_custom_agent_revision_number"))


# V12: separate entity families with tenant-composite, revision-pinned sources.
HR_TABLES = {}
for family, states in (("requirements", "'draft','active','closed','archived'"),
                       ("role_knowledge", "'active','archived'"),
                       ("job_descriptions", "'draft','archived'")):
    name = "hr_" + family
    head = Table(name, metadata,
        Column("id", String(80), primary_key=True),
        Column("workspace_id", String(80), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False),
        Column("revision", Integer, nullable=False),
        Column("status", String(20), nullable=False),
        Column("created_by_user_id", String(80), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        Column("created_at", String(40), nullable=False),
        UniqueConstraint("id", "workspace_id", name="uq_" + name + "_tenant"),
        CheckConstraint("revision >= 1", name="ck_" + name + "_revision"),
        CheckConstraint("status IN (" + states + ")", name="ck_" + name + "_status"))
    Index("ix_" + name + "_workspace", head.c.workspace_id, head.c.created_at)
    revisions = Table(name + "_revisions", metadata,
        Column("record_id", String(80), primary_key=True),
        Column("revision", Integer, primary_key=True),
        Column("workspace_id", String(80), nullable=False),
        Column("updated_by_user_id", String(80), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        Column("updated_at", String(40), nullable=False),
        Column("payload", json_type, nullable=False),
        UniqueConstraint("record_id", "revision", "workspace_id", name="uq_" + name + "_source"),
        ForeignKeyConstraint(["record_id", "workspace_id"], [name + ".id", name + ".workspace_id"], ondelete="RESTRICT"),
        CheckConstraint("revision >= 1", name="ck_" + name + "_revision_number"))
    if family == "job_descriptions":
        for source, target, required in (("requirement", "hr_requirements_revisions", True),
                                         ("knowledge", "hr_role_knowledge_revisions", False)):
            revisions.append_column(Column(source + "_id", String(80), nullable=not required))
            revisions.append_column(Column(source + "_revision", Integer, nullable=not required))
            revisions.append_constraint(ForeignKeyConstraint(
                [source + "_id", source + "_revision", "workspace_id"],
                [target + ".record_id", target + ".revision", target + ".workspace_id"], ondelete="RESTRICT"))
        revisions.append_constraint(CheckConstraint(
            "(knowledge_id IS NULL) = (knowledge_revision IS NULL)", name="ck_hr_knowledge_pair"))
    Index("ix_" + name + "_revision_workspace", revisions.c.workspace_id, revisions.c.record_id)
    HR_TABLES[family] = (head, revisions)


# V13: submissions and transition events are append-only. Status is derived from events.
hr_review_submissions = Table("hr_review_submissions", metadata,
    Column("id", String(80), primary_key=True),
    Column("workspace_id", String(80), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False),
    Column("jd_id", String(80), nullable=False),
    Column("jd_revision", Integer, nullable=False),
    Column("requested_by_user_id", String(80), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
    Column("submitted_at", String(40), nullable=False),
    Column("ai_run_ids", json_type, nullable=False),
    UniqueConstraint("id", "workspace_id", name="uq_hr_review_submission_tenant"),
    UniqueConstraint("jd_id", "jd_revision", "workspace_id", name="uq_hr_review_submitted_revision"),
    ForeignKeyConstraint(["jd_id", "jd_revision", "workspace_id"],
        ["hr_job_descriptions_revisions.record_id", "hr_job_descriptions_revisions.revision",
         "hr_job_descriptions_revisions.workspace_id"], ondelete="RESTRICT"),
    CheckConstraint("jd_revision >= 1", name="ck_hr_review_revision"))
Index("ix_hr_review_workspace", hr_review_submissions.c.workspace_id, hr_review_submissions.c.submitted_at)
hr_review_events = Table("hr_review_events", metadata,
    Column("id", String(80), primary_key=True),
    Column("workspace_id", String(80), nullable=False),
    Column("submission_id", String(80), nullable=False),
    Column("version", Integer, nullable=False),
    Column("actor_user_id", String(80), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
    Column("occurred_at", String(40), nullable=False),
    Column("action", String(30), nullable=False),
    Column("from_status", String(30), nullable=False),
    Column("to_status", String(30), nullable=False),
    Column("notes", String(4000), nullable=False),
    UniqueConstraint("submission_id", "version", name="uq_hr_review_event_version"),
    ForeignKeyConstraint(["submission_id", "workspace_id"],
        ["hr_review_submissions.id", "hr_review_submissions.workspace_id"], ondelete="RESTRICT"),
    CheckConstraint("version >= 1", name="ck_hr_review_event_version"),
    CheckConstraint("length(notes) <= 4000 AND (action = 'submit' OR length(trim(notes)) > 0)",
                    name="ck_hr_review_notes"),
    CheckConstraint("(version = 1 AND action = 'submit' AND from_status = 'draft' AND to_status = 'pending_review') OR "
        "(version = 2 AND from_status = 'pending_review' AND ((action = 'recommend' AND to_status = 'reviewed') OR "
        "(action = 'request_changes' AND to_status = 'changes_requested') OR (action = 'reject' AND to_status = 'rejected'))) OR "
        "(version = 3 AND from_status = 'reviewed' AND ((action = 'approve' AND to_status = 'approved') OR "
        "(action = 'request_changes' AND to_status = 'changes_requested') OR (action = 'reject' AND to_status = 'rejected')))",
        name="ck_hr_review_transition"))
Index("ix_hr_review_event_workspace", hr_review_events.c.workspace_id, hr_review_events.c.submission_id)
