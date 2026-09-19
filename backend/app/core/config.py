"""
app/core/config.py

Centralized settings for the whole backend. This is the ONLY file that
should read from environment variables directly — every other module
imports `settings` from here instead of calling os.getenv() itself.

Why this matters for the team:
    Anything that changes between a teammate's laptop, the deployed demo
    server, and production later (ports, secrets, DB location, allowed
    frontend origins) lives here and ONLY here. When someone says
    "why isn't X connecting", this is the first (and usually only) file
    to check.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # App metadata — safe defaults, rarely need to change
    # ------------------------------------------------------------------
    APP_NAME: str = "Multi-Agent AI Environment Simulator API"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # ------------------------------------------------------------------
    # USER-DEFINED — CORS / allowed frontend origins
    # ------------------------------------------------------------------
    # Add every URL the frontend will actually be served from.
    #   - Vite dev server default is http://localhost:5173
    #   - Add your deployed frontend URL here once you have one
    #     (e.g. Vercel/Netlify preview URL, or your college demo server)
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",   # <-- LOCATION-CHANGING: Vite dev server. Update if you run on a different port.
        "http://127.0.0.1:5173",
        "https://ai-agent-environment-simulator.vercel.app",
        # "https://your-deployed-frontend.example.com",  # <-- USER-DEFINED: uncomment + fill in once deployed
    ]

    # ------------------------------------------------------------------
    # USER-DEFINED — Database connection
    # ------------------------------------------------------------------
    # Local dev default is SQLite (zero setup). Swap to Postgres when the
    # storage layer (app/storage/) is actually implemented.
    #   Postgres example:
    #   DATABASE_URL = "postgresql://<user>:<password>@<host>:<port>/<db_name>"
    DATABASE_URL: str = "sqlite:///./simulator.db"  # <-- USER-DEFINED: change to your Postgres URL when ready

    # ------------------------------------------------------------------
    # USER-DEFINED — LLM provider
    # ------------------------------------------------------------------
    # ACTIVE default: a local Ollama server (matches the team's validated
    # setup — Ollama + gemma2:2b). Start it before running the backend:
    #     ollama serve            # in its own terminal
    #     ollama pull gemma2:2b    # one-time, if not already pulled
    OLLAMA_HOST: str = "http://localhost:11434"  # <-- LOCATION-CHANGING: change if Ollama runs elsewhere (e.g. a shared team server)
    OLLAMA_MODEL: str = "gemma2:2b"                # <-- USER-DEFINED: must match a model you've actually pulled — see `ollama list`

    # RESERVED — alternate: cloud providers, if the team switches later
    # (better quality, no local GPU needed, costs money per call).
    # Not used by app/agents/llm_client.py right now.
    ANTHROPIC_API_KEY: str = ""   # <-- USER-DEFINED: set in .env if you switch to Claude, never commit the real value
    OPENAI_API_KEY: str = ""      # <-- USER-DEFINED: set in .env if you switch to GPT

    # ------------------------------------------------------------------
    # WebSocket
    # ------------------------------------------------------------------
    WEBSOCKET_PATH: str = "/ws/live"  # frontend's useLiveSocket.js must point at this same path

    # ------------------------------------------------------------------
    # USER-DEFINED — Server host/port (used by run.py, not by uvicorn CLI)
    # ------------------------------------------------------------------
    HOST: str = "0.0.0.0"   # <-- LOCATION-CHANGING: keep 0.0.0.0 for containers/deployment, use 127.0.0.1 for local-only
    PORT: int = 8000        # <-- LOCATION-CHANGING: change if 8000 is taken, and update the frontend's VITE_API_BASE_URL to match

    model_config = SettingsConfigDict(
        env_file=".env",       # values here are overridden by a real .env file if present
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Import this single instance everywhere: `from app.core.config import settings`
settings = Settings()
