# Backend — Multi-Agent AI Environment Simulator

FastAPI backend. Phase 1 scope: API shape + mock data + WebSocket
plumbing, so the frontend has a real server to point at. Storage and
the LangGraph agent framework are scaffolded but intentionally **not**
implemented yet — see the "RESERVED" sections below.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then fill in real values, see comments inside
python run.py
```

Server runs at `http://localhost:8000` by default (change via `.env`, see
`app/core/config.py`). Interactive API docs at `http://localhost:8000/docs`.

## Folder map

```
app/
├── main.py              # FastAPI app, CORS, router registration, WebSocket endpoint
├── core/
│   └── config.py         # ALL environment/location-specific values live here
├── models/
│   └── schemas.py         # Pydantic models — must mirror the frontend's TS contracts
├── api/routes/
│   ├── agents.py           # GET/POST agents, GET relationships
│   ├── tasks.py             # GET/POST tasks
│   ├── messages.py           # GET messages
│   └── simulation.py          # GET stats/activity, POST pause/resume/stop
├── websocket/
│   └── manager.py         # Live-update broadcaster — fully functional, no dependencies
├── storage/               # RESERVED — SQLAlchemy models + DB session (see database.py checklist)
│   ├── database.py
│   └── models.py
└── agents/                # RESERVED — LangGraph orchestrator goes here (see orchestrator.py)
    └── orchestrator.py
```

## What's real vs. reserved right now

| Piece | Status |
|---|---|
| API routes (`agents`, `tasks`, `messages`, `simulation`) | **Working**, backed by in-memory mock data |
| WebSocket broadcast (`websocket/manager.py`) | **Working** — connect from the frontend and call any route's POST/create endpoints to see broadcasts fire |
| CORS / config (`core/config.py`) | **Working** — update `CORS_ORIGINS` if your frontend runs on a different port |
| Storage (`storage/`) | **Reserved** — commented-out SQLAlchemy skeleton, follow the checklist in `database.py` to activate |
| Agent framework (`agents/`) | **Reserved** — commented-out LangGraph skeleton, Member C fills this in once the standalone framework prototype is validated |

## Every place you'll need to change a value

Search the codebase for `USER-DEFINED` and `LOCATION-CHANGING` comments —
every environment-specific or deployment-specific line is tagged with one
of those two markers so nothing is buried.
