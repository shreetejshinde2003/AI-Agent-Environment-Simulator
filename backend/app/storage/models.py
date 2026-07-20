"""
app/storage/models.py

RESERVED — SQLAlchemy ORM models go here. Not activated yet (see the
checklist in app/storage/database.py).

When you do build these out, mirror app/models/schemas.py field-for-field
so the DB row -> Pydantic response conversion is a straight mapping with
no surprises. Suggested table names are already sketched below as
commented-out class stubs — uncomment and fill in as needed.
"""

# from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey
# from app.storage.database import Base
#
#
# class AgentModel(Base):
#     __tablename__ = "agents"
#
#     id = Column(String, primary_key=True)
#     name = Column(String, nullable=False)
#     role = Column(String, nullable=False)
#     status = Column(String, nullable=False, default="idle")
#     color = Column(String, nullable=False)
#     icon = Column(String, nullable=True)
#
#
# class TaskModel(Base):
#     __tablename__ = "tasks"
#
#     id = Column(String, primary_key=True)
#     directive = Column(String, nullable=False)
#     assigned_agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
#     status = Column(String, nullable=False, default="queued")
#     priority = Column(String, nullable=False, default="medium")
#     started_at = Column(DateTime, nullable=False)
#     duration_seconds = Column(Integer, default=0)
#     progress_percent = Column(Integer, default=0)
#
#
# class MessageModel(Base):
#     __tablename__ = "messages"
#
#     id = Column(String, primary_key=True)
#     from_agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
#     to_agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
#     kind = Column(String, nullable=False)
#     content = Column(String, nullable=False)
#     timestamp = Column(DateTime, nullable=False)
#
#
# class ActivityEventModel(Base):
#     __tablename__ = "activity_events"
#
#     id = Column(String, primary_key=True)
#     agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
#     text = Column(String, nullable=False)
#     timestamp = Column(DateTime, nullable=False)
