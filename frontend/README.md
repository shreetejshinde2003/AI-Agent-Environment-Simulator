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
│       └── ConnectionBadge.jsx        # real Live/Offline/Demo badge, replaces hardcoded "Live" pills
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
1. Start `/backend` (see its own README) — `python run.py`.
2. Start this frontend — `npm run dev`.
3. Within ~5 seconds, the connection badge in the Topbar flips from
   "Disconnected" to "Connected" and real data (currently the backend's
   mock agents/tasks, until storage + the agent framework are wired up
   on the backend side) starts flowing in.

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
