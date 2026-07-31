# Backend — Multi-Agent AI Environment Simulator

FastAPI backend. LLM calls go through a local Ollama server
(gemma2:2b) — see `app/agents/llm_client.py`. The Research Agent is
fully wired up end to end: create a task, it actually runs, and the
result (or a real error) shows up on the dashboard, not just the terminal.

## Setup

```bash
# 1. Ollama, in its own terminal — leave this running
ollama serve
ollama pull gemma2:2b   # one-time, if not already pulled

# 2. Backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then fill in real values, see comments inside
python run.py
```

Server runs at `http://localhost:8000` by default (change via `.env`, see
`app/core/config.py`). Interactive API docs at `http://localhost:8000/docs`.

## Important fix: camelCase contract (read this if the frontend ever shows "undefined")

Every schema in `app/models/schemas.py` inherits from `CamelModel`, not
`BaseModel`. Python fields stay snake_case (`total_agents`), but JSON
output is automatically camelCase (`totalAgents`) — because the
frontend is JavaScript and reads camelCase. A plain `BaseModel` sends
snake_case JSON by default, which silently doesn't match what React
code reads (`stats.totalAgents` would be `undefined` if the wire format
was `total_agents`). If you add a new field, keep it snake_case in
Python — `CamelModel` handles the conversion. Don't name Python fields
camelCase to "fix" this; that fights the language's own convention and
isn't the actual problem.

## Folder map

```
app/
├── main.py              # FastAPI app, CORS, router registration, WebSocket endpoint
├── core/
│   └── config.py         # ALL environment/location-specific values live here (incl. OLLAMA_HOST/MODEL)
├── models/
│   └── schemas.py         # Pydantic models — CamelModel base, see the contract note above
├── api/routes/
│   ├── agents.py           # GET/POST agents (roster + LIVE status merged from stats_tracker)
│   ├── tasks.py             # POST actually runs the assigned agent in the background — see below
│   ├── messages.py           # GET messages
│   └── simulation.py          # GET stats (live-computed agent counts) /activity, POST pause/resume/stop
├── websocket/
│   └── manager.py         # Live-update broadcaster — fully functional
├── storage/               # RESERVED — SQLAlchemy models + DB session (see database.py checklist)
│   ├── database.py
│   └── models.py
└── agents/
    ├── llm_client.py         # ACTIVE — calls Ollama (gemma2:2b). Swap to a cloud provider here, one file.
    ├── base_agent.py          # Shared class: timing + stats + live status capture for every agent
    ├── stats_tracker.py        # Real per-agent stats + live status, zero/idle by default
    ├── research_agent.py        # ACTIVE — the first working agent, calls Ollama for real
    ├── data_agent.py              # RESERVED — same pattern as research_agent.py, not yet activated
    ├── web_search_agent.py         # RESERVED
    ├── analysis_agent.py            # RESERVED
    ├── summarizer_agent.py           # RESERVED
    ├── report_agent.py                # RESERVED
    └── orchestrator.py                 # RESERVED — LangGraph wiring across all six agents
```

## How task execution actually works now (`api/routes/tasks.py`)

`POST /api/v1/tasks` creates the task (status `queued`), returns
immediately, then runs the assigned agent as a FastAPI background task:

1. Task flips to `in_progress`, broadcast over WebSocket.
2. The agent (currently only `research` is real — see
   `_IMPLEMENTED_AGENTS` in `tasks.py`) actually runs via `agent.run(...)`.
3. On success: `task.output` is set to the agent's real response text,
   status becomes `completed`.
4. On failure (e.g. Ollama not running): `task.error` is set to the
   real exception message, status becomes `failed` — this is what
   surfaces "Ollama not reachable" on the dashboard instead of leaving
   you staring at a terminal.
5. Every transition broadcasts over WebSocket, and `hooks/useLiveSocket.js`
   on the frontend refetches immediately — no polling delay.

Assigning a task to any agent other than `research` right now creates
the task successfully, then it visibly fails a moment later with
`"Agent '<id>' is not implemented yet"` — that's the correct, honest
behavior until more agents are activated, not a bug.

## What's real vs. reserved right now

| Piece | Status |
|---|---|
| API routes (`agents`, `tasks`, `messages`, `simulation`) | **Working**, all starting from a genuine zero/empty baseline |
| Task execution (`tasks.py`'s `_run_task`) | **Working** for the Research agent — real Ollama call, real output/error written back |
| WebSocket broadcast (`websocket/manager.py`) | **Working** |
| CORS / config (`core/config.py`) | **Working** |
| Agent stats + live status (`agents/stats_tracker.py`, `agents/base_agent.py`) | **Working** — genuinely zero/idle until an agent actually runs |
| LLM client (`agents/llm_client.py`) | **Working (Ollama)** — swap to a cloud provider by editing this one file |
| Research agent (`agents/research_agent.py`) | **Working** |
| The other five agents (`agents/*_agent.py`) | **Reserved** — same pattern as research_agent.py, `process()` raises `NotImplementedError` until activated |
| Orchestrator (`agents/orchestrator.py`) | **Reserved** — commented LangGraph skeleton, needed once more than one agent is active and they need to hand off to each other |
| Storage (`storage/`) | **Reserved** — commented-out SQLAlchemy skeleton |

## Activating the remaining five agents (in order, per agent)

1. Copy `research_agent.py`'s structure into the target agent file — the prompt and model choice are already written, just uncomment.
2. Add the agent to `tasks.py`'s `_IMPLEMENTED_AGENTS` dict — one line.
3. That's it — stats, status, WebSocket broadcast, and dashboard display all already work generically for any agent in `_IMPLEMENTED_AGENTS`.

Once more than one agent is active and they need to hand off work to
each other (not just run independently), that's when `orchestrator.py`
actually needs to be built out — a single active agent doesn't need
LangGraph yet.
## Every place you'll need to change a value

Search the codebase for `USER-DEFINED` and `LOCATION-CHANGING` comments —
every environment-specific or deployment-specific line is tagged with one
of those two markers so nothing is buried. This includes model choices
and prompts inside `agents/llm_client.py` and each `agents/*_agent.py` file.
