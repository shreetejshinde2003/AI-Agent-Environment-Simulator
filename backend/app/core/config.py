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
    # Local default is SQLite. A supplied PostgreSQL URL activates psycopg;
    # never put production credentials in this source file.
    DATABASE_URL: str = "sqlite:///./simulator.db"
    # Deliberately gated until PostgreSQL persistence/security acceptance passes.
    LANGGRAPH_RUNTIME_ENABLED: bool = False
    CHECKPOINT_DATABASE_URL: str = ""
    CHECKPOINT_SCHEMA: str = "langgraph_checkpoints"
    # Optional private runtime directory containing the six benchmark JSON files.
    BENCHMARK_DATA_DIR: str | None = None

    # ------------------------------------------------------------------
    # USER-DEFINED — LLM provider
    # ------------------------------------------------------------------
    # ACTIVE: Groq's hosted API (free tier, no card required as of
    # 2026-09). Get a key at console.groq.com/keys and set it in .env
    # for local dev AND in Railway's Variables tab for the deployed
    # backend (Railway never reads your local .env).
    GROQ_API_KEY: str = ""                              # <-- USER-DEFINED: from console.groq.com/keys — never commit the real value
    GROQ_MODEL: str =  "openai/gpt-oss-120b"         # <-- USER-DEFINED: verify still live at console.groq.com/docs/models
    GROQ_FAST_MODEL: str = "openai/gpt-oss-20b"        # <-- USER-DEFINED: verify still live at console.groq.com/docs/models

    # RESERVED — local Ollama (previously active, switched off
    # 2026-09-25 because Railway can't reach a laptop's localhost).
    # Kept in case the team ever falls back to a local model.
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma2:2b"

    # RESERVED — Anthropic alternate, if the team switches off Groq
    # later for quality over speed. Not used by llm_client.py right now.
    ANTHROPIC_API_KEY: str = ""   # <-- USER-DEFINED: set in .env if you switch to Claude, never commit the real value
    OPENAI_API_KEY: str = ""      # <-- USER-DEFINED: set in .env if you switch to GPT

    # ------------------------------------------------------------------
    # Google OAuth / OpenID Connect
    # ------------------------------------------------------------------
    # Secrets belong in backend/.env locally and Railway Variables in
    # production. Never commit the real client secret.
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = (
        "http://localhost:8000/api/v1/auth/google/callback"
    )
    FRONTEND_URL: str = "http://localhost:5173"

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
