"""
run.py

Convenience entrypoint: `python run.py`
Equivalent to running `uvicorn app.main:app --reload --host <HOST> --port <PORT>`
but reads host/port from app/core/config.py so there's one source of truth.
"""

import uvicorn

from app.core.config import settings

if __name__ == "__main__":
    from app.experiments.demo_budget import bounded_demo, claim_local_runtime, release_local_runtime
    demo = settings.RESEARCH_LIVE_ENABLED and bounded_demo()
    if demo:
        claim_local_runtime(settings.DATABASE_URL)
    try:
        uvicorn.run(
            "app.main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=False if demo else settings.DEBUG,
            workers=1 if demo else None,
        )
    finally:
        if demo:
            release_local_runtime()
