"""Version 2 operational tables; benchmark records never enter this schema."""

from sqlalchemy import (JSON, Boolean, Column, Float, ForeignKey, Index, Integer,
                        MetaData, String, Table, Text)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()
json_type = JSON().with_variant(JSONB, "postgresql")

schema_version = Table("schema_version", metadata,
    Column("version", Integer, primary_key=True), Column("applied_at", String(40), nullable=False))
dataset_registry = Table("dataset_registry", metadata,
    Column("dataset_id", String(80), primary_key=True), Column("name", String(120), nullable=False),
    Column("family", String(40), nullable=False), Column("size_variant", String(20), nullable=False),
    Column("source_filename", String(120), nullable=False), Column("record_count", Integer, nullable=False),
    Column("schema_columns", json_type, nullable=False), Column("checksum", String(64), nullable=False),
    Column("active", Boolean, nullable=False), Column("imported_at", String(40), nullable=False),
    Column("quality", json_type, nullable=False))
simulations = Table("simulations", metadata,
    Column("id", String(80), primary_key=True), Column("owner_id", String(80)),
    Column("dataset_id", String(80), ForeignKey("dataset_registry.dataset_id", ondelete="SET NULL")),
    Column("dataset_checksum", String(64)), Column("status", String(30), nullable=False),
    Column("execution_mode", String(30), nullable=False), Column("task_type", String(80)),
    Column("created_at", String(40), nullable=False), Column("started_at", String(40)),
    Column("completed_at", String(40)), Column("payload", json_type, nullable=False))
Index("ix_simulations_status_created", simulations.c.status, simulations.c.created_at)
Index("ix_simulations_dataset", simulations.c.dataset_id)
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
    Column("id", String(80), primary_key=True), Column("filename", String(255), nullable=False),
    Column("format", String(20), nullable=False), Column("size_bytes", Integer, nullable=False),
    Column("created_at", String(40), nullable=False), Column("payload", json_type, nullable=False))
simulation_uploads = Table("simulation_uploads", metadata,
    Column("simulation_id", String(80), ForeignKey("simulations.id", ondelete="CASCADE"), primary_key=True),
    Column("upload_id", String(80), ForeignKey("uploads.id", ondelete="RESTRICT"), primary_key=True))
agent_roster = Table("agent_roster", metadata,
    Column("id", String(80), primary_key=True), Column("payload", json_type, nullable=False))
