"""
run.py

Convenience entrypoint: `python run.py`
Equivalent to running `uvicorn app.main:app --reload --host <HOST> --port <PORT>`
but reads host/port from app/core/config.py so there's one source of truth.
"""

import uvicorn

from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,   # <-- LOCATION-CHANGING: set via .env, see app/core/config.py
        port=settings.PORT,   # <-- LOCATION-CHANGING: set via .env, see app/core/config.py
        reload=settings.DEBUG,
    )
