import AppShell from "./layout/AppShell";
import RunPicker from "./components/dashboard/RunPicker";
import { SimulationProvider, useSimulation } from "./context/SimulationContext";
import LiveSimulation from "./pages/LiveSimulation";
import TaskSummary from "./pages/TaskSummary";
import Agents from "./pages/Agents";
import Messages from "./pages/Messages";
import Logs from "./pages/Logs";
import Replay from "./pages/Replay";
import Settings from "./pages/Settings";
import { PrivacyPolicy, TermsOfService } from "./pages/LegalPages";
import Login from "./pages/Login";
import { useAuth } from "./hooks/useAuth";
import "./components/dashboard/SimulationWorkspace.css";
const PAGES = {live: LiveSimulation, "task-summary": TaskSummary, agents: Agents,
  messages: Messages, logs: Logs, replay: Replay, settings: Settings};
function AppContent({ authUser, onSignOut }) {
  const {
    activePage,
    setActivePage,
    selectedTask,
    tasks,
    selectTask,
    error,
    socketStatus,
    isLoading,
    lastRefreshedAt,
  } = useSimulation();

  const Page = PAGES[activePage] ?? LiveSimulation;

  const user = {
    name:
      authUser?.displayName ||
      authUser?.email ||
      "Authenticated user",
    role: authUser?.email ?? "Signed in",
    avatarUrl: authUser?.profilePicture ?? null,
    onLogout: onSignOut,
  };

  return (
    <AppShell
      activePage={activePage}
      onNavigate={setActivePage}
      user={user}
      topbarProps={{
        goal:
          activePage === "live"
            ? null
            : selectedTask?.directive ??
              "Create a simulation to get started",
        onToggleReplay: () =>
          setActivePage("replay"),
      }}
    >
      {activePage !== "live" && (
        <div className="run-toolbar">
          <RunPicker
            tasks={tasks}
            selectedTask={selectedTask}
            onSelect={selectTask}
            isLoading={isLoading}
            loadError={!!error && !tasks.length}
          />

          <span
            className="muted"
            role="status"
          >
            {socketStatus === "connected"
              ? "Live events connected"
              : socketStatus === "connecting"
                ? "Connecting live events… REST refresh remains available."
                : "Live events offline · REST refresh every 5s"}
          </span>
        </div>
      )}

      {error && (
        <p
          className="run-error"
          role="alert"
        >
          {lastRefreshedAt
            ? `Cannot refresh backend data. Last successful refresh: ${new Date(lastRefreshedAt).toLocaleString()}. Displayed records may be stale.`
            : "Cannot load backend data."}{" "}
          {error.message}
        </p>
      )}

      <Page />
    </AppShell>
  );
}
function AuthenticatedApp() {
  const {
    user,
    status,
    error,
    signOut,
  } = useAuth();

  if (status === "loading") {
    return (
      <main className="login-page">
        <section className="login-panel">
          <p className="login-eyebrow">
            Agent Environment Simulator
          </p>
          <h1>Checking session…</h1>
        </section>
      </main>
    );
  }

  if (
    status === "anonymous" ||
    status === "error" ||
    !user
  ) {
    return <Login error={error} />;
  }

  return (
    <SimulationProvider>
      <AppContent
        authUser={user}
        onSignOut={signOut}
      />
    </SimulationProvider>
  );
}

export default function App() {
  const path =
    window.location.pathname.replace(
      /\/+$/,
      "",
    ) || "/";

  if (path === "/privacy") {
    return <PrivacyPolicy />;
  }

  if (path === "/terms") {
    return <TermsOfService />;
  }

  return <AuthenticatedApp />;
}
