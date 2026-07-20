import AppShell, { useActivePage } from "./layout/AppShell";
import { SimulationProvider, useSimulation } from "./context/SimulationContext";

import LiveSimulation from "./pages/LiveSimulation";
import TaskSummary from "./pages/TaskSummary";
import Agents from "./pages/Agents";
import Messages from "./pages/Messages";
import Logs from "./pages/Logs";
import Replay from "./pages/Replay";
import Settings from "./pages/Settings";

// Maps each Sidebar nav id to the page component it should render.
// Add a new entry here whenever a new nav item is added to layout/Sidebar.jsx.
const PAGES = {
  live: LiveSimulation,
  "task-summary": TaskSummary,
  agents: Agents,
  messages: Messages,
  logs: Logs,
  replay: Replay,
  settings: Settings,
};

// USER-DEFINED: swap for a real logged-in user once auth exists.
const CURRENT_USER = { name: "Parag Kulkarni", role: "Administrator" };

/**
 * Decides what the Topbar's "Current Goal" line should say.
 *
 * RESERVED: the backend's SimulationStats schema (see
 * backend/app/models/schemas.py) has no "goal" field yet — there's no
 * real place for this text to come from until app/agents/orchestrator.py
 * exists and exposes the orchestrator's current high-level goal. Until
 * then, this returns honest status text instead of a fabricated goal.
 */
function resolveGoalText({ isDemoMode, connectionStatus }) {
  if (isDemoMode) return "Market Research & Competitor Analysis (Demo)";
  if (connectionStatus === "connecting") return "Connecting to backend…";
  if (connectionStatus !== "connected") return "Backend disconnected — no active goal";
  return "No active goal set";
}

function AppContent() {
  const [activePage, setActivePage] = useActivePage("live");
  const { stats, connectionStatus, isDemoMode } = useSimulation();

  const PageComponent = PAGES[activePage] ?? LiveSimulation;

  return (
    <AppShell
      activePage={activePage}
      onNavigate={setActivePage}
      user={CURRENT_USER}
      topbarProps={{
        goal: resolveGoalText({ isDemoMode, connectionStatus }),
        isPaused: stats.status === "paused",
        // RESERVED: no real notification system exists yet — this
        // stays 0 (not a fabricated count) until one is built.
        notificationCount: 0,
        onToggleReplay: () => setActivePage("replay"),
        onTogglePause: () => console.log("TODO: call apiClient.pauseSimulation() / resumeSimulation()"),
        onStop: () => console.log("TODO: call apiClient.stopSimulation()"),
        onOpenNotifications: () => console.log("TODO: open notifications panel"),
      }}
    >
      <PageComponent />
    </AppShell>
  );
}

export default function App() {
  return (
    <SimulationProvider>
      <AppContent />
    </SimulationProvider>
  );
}
