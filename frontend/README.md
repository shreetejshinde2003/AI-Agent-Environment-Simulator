# Frontend — Multi-Agent AI Environment Simulator

React + Vite dashboard matching the reference mockup. Runs entirely on
mock data today — no backend connection required to develop or demo it.

## Setup

```bash
npm install
npm run dev
```

Opens at `http://localhost:5173`.

## Folder map

```
src/
├── index.css                      # design tokens (colors, spacing, type scale)
├── App.jsx                         # page router + SimulationProvider wrapper
├── main.jsx
│
├── layout/                         # chrome that wraps every page
│   ├── AppShell.jsx                  # composes Sidebar + Topbar + page content
│   ├── Sidebar.jsx                    # nav rail + Simulation Info + user footer
│   └── Topbar.jsx                      # current goal + playback controls
│
├── pages/                          # one file per Sidebar nav item
│   ├── LiveSimulation.jsx            # the main dashboard (fully built)
│   ├── TaskSummary.jsx                 # RESERVED — placeholder
│   ├── Agents.jsx                       # RESERVED — placeholder
│   ├── Messages.jsx                      # RESERVED — placeholder
│   ├── Logs.jsx                           # RESERVED — placeholder
│   ├── Replay.jsx                          # RESERVED — placeholder
│   └── Settings.jsx                         # RESERVED — placeholder
│
├── components/
│   ├── dashboard/                  # everything specific to simulation data
│   │   ├── StatsCardRow.jsx / StatsCard.jsx
│   │   ├── AgentRelationshipGraph.jsx / AgentNode.jsx / GraphLegend.jsx
│   │   ├── TaskDetailsPanel.jsx
│   │   ├── MessageFlowFeed.jsx
│   │   ├── SimulationTimeline.jsx
│   │   ├── ActivityFeed.jsx
│   │   ├── SimulationInfoPanel.jsx
│   │   └── QuickActions.jsx
│   └── common/                     # generic, reusable UI pieces
│       ├── Badge.jsx / Card.jsx / Button.jsx / ProgressBar.jsx / Avatar.jsx
│       ├── EmptyState.jsx            # honest "nothing here yet" state, used by every panel
│       ├── ConnectionBadge.jsx        # real Live/Offline/Demo badge, replaces hardcoded "Live" pills
│       └── Modal.jsx                   # generic overlay dialog, used by the two forms below
│   dashboard/ also has:
│       ├── CreateTaskModal.jsx        # real "Create Task" form → POST /api/v1/tasks
│       └── AddAgentModal.jsx           # real "Add Agent" form → POST /api/v1/agents
│
├── context/
│   └── SimulationContext.jsx       # global simulation state, wraps useSimulationData()
│
├── hooks/
│   ├── useBackendConnection.js      # polls backend /health, reports connecting/connected/disconnected
│   ├── useSimulationData.js         # real fetches when connected; honest zero-state when not; demo mode opt-in
│   └── useLiveSocket.js              # WebSocket stub — disabled until backend is live
│
├── services/
│   ├── mockData.js                 # DEMO MODE ONLY — sample data, not the default anymore
│   └── apiClient.js                 # real API calls — used by default once the backend is reachable
│
└── utils/
    ├── colors.js                    # agent-role → color (single source of truth)
    └── formatTime.js                  # shared time/duration formatting
```

## Real-time data vs. Demo Mode

**Default behavior:** the app tries to reach the backend at
`VITE_API_BASE_URL` on load, and every 5 seconds after that. If the
backend isn't reachable — which is the case if you've just cloned this
repo and haven't started `/backend` yet — every number on the
dashboard is a genuine `0` or an explicit empty state ("No agents
connected", "No messages yet", etc). It does **not** show sample data
by default. A real-time dashboard that shows "6/7 agents active" when
nothing is running is lying, so this app simply won't do that.

**To see real data:**
1. Start Ollama — `ollama serve`, and `ollama pull gemma2:2b` if you haven't.
2. Start `/backend` (see its own README) — `python run.py`.
3. Start this frontend — `npm run dev`.
4. Within ~5 seconds, the connection badge in the Topbar flips from
   "Disconnected" to "Connected".
5. Use the **Create Task** quick action (bottom-right of the dashboard)
   to assign a real directive to the Research Agent — the result (or a
   real error, e.g. if Ollama isn't running) appears in the **Task
   Details** panel's new "Agent Output" section within a few seconds,
   pushed live over WebSocket — no page refresh, no polling delay.

**To preview the UI without any backend at all** (e.g. showing a
teammate the design, or working on styling in isolation): set
`VITE_DEMO_MODE=true` in `.env`, or append `?demo=true` to the dev
server URL for a one-off session. Every page shows an unmissable
"Demo Mode" banner/badge whenever this is active, specifically so demo
data can never be mistaken for a live feed.

| Scenario | What you see |
|---|---|
| No backend running, demo mode off (default) | Real `0`s / empty states everywhere, "Disconnected" badge |
| Backend running, demo mode off | Real data from the backend, "Connected" badge, polling every 5s |
| Demo mode on (`?demo=true` or env var) | Sample data, "Demo Mode" badge everywhere, backend not contacted |

## Switching from mock data to the real backend

This is now automatic — see the table above. The only manual step left
is starting the backend; the frontend detects it on its own via
`hooks/useBackendConnection.js`.

No component outside `hooks/` and `services/` needs to change when the
backend comes online — that's the entire point of routing all data
through `useSimulation()`.

## Where to look for "why is this hardcoded"

Every environment- or deployment-specific value is tagged with one of
two comment markers — search the codebase for them:
- `USER-DEFINED` — a value a person has to decide (colors for new agent
  roles, which page a button navigates to, mock vs. real data toggle)
- `LOCATION-CHANGING` — a value that differs by machine/environment
  (API base URL, WebSocket URL, dev server port)

## Field naming contract with the backend (important)

Every field this frontend reads is camelCase (`totalAgents`,
`assignedAgentId`) because that's the JS convention. The backend's
Pydantic models are internally snake_case (Python convention) but
convert to camelCase automatically via a shared `CamelModel` base — see
`backend/app/models/schemas.py`. If a new field ever shows up as
`undefined` on this side despite the backend responding 200 OK, check
that the backend model actually inherits `CamelModel` before assuming
the frontend is broken — that mismatch is a real bug class that's bitten
this project before.
