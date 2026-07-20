"""
app/storage/database.py

RESERVED — storage is not wired into the running app yet (Phase 1 is
frontend + API shape only). This file is a ready-to-activate skeleton so
whoever picks up storage doesn't have to make structural decisions,
just fill in the model classes in storage/models.py and flip the
switch below.

--------------------------------------------------------------------
HOW TO ACTIVATE THIS LATER (checklist):
--------------------------------------------------------------------
1. Add real ORM model classes in app/storage/models.py (Base subclasses).
2. Uncomment the engine/session code below.
3. In app/main.py, uncomment the `Base.metadata.create_all(bind=engine)`
   line (or set up Alembic migrations instead — recommended once the
   schema stabilizes).
4. In each app/api/routes/*.py file, replace the in-memory mock data
   with a real DB query using `Depends(get_db)`.
5. Update DATABASE_URL in .env — see app/core/config.py for the
   Postgres connection string format.
"""

from app.core.config import settings

# ----------------------------------------------------------------------
# UNCOMMENT EVERYTHING BELOW ONCE storage/models.py HAS REAL MODELS
# ----------------------------------------------------------------------

# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker, declarative_base
#
# # USER-DEFINED: connect_args is only needed for SQLite (single-threaded
# # check). Remove connect_args entirely once you switch to Postgres.
# engine = create_engine(
#     settings.DATABASE_URL,  # <-- LOCATION-CHANGING: set via .env, see app/core/config.py
#     connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
# )
#
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Base = declarative_base()
#
#
# def get_db():
#     """FastAPI dependency — use as: def route(db: Session = Depends(get_db))"""
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()
