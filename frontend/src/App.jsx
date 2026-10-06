import AppShell from "./layout/AppShell";
import RunPicker from "./components/dashboard/RunPicker";
import { SimulationProvider, useSimulation } from "./context/SimulationContext";
import WorkspaceProvider from "./context/WorkspaceProvider";
import { useWorkspace } from "./hooks/useWorkspace";
import LiveSimulation from "./pages/LiveSimulation";
import TaskSummary from "./pages/TaskSummary";
import Hiring from "./pages/Hiring";
import Agents from "./pages/Agents";
import Messages from "./pages/Messages";
import Logs from "./pages/Logs";
import Replay from "./pages/Replay";
import RecycleBin from "./pages/RecycleBin";
import Settings from "./pages/Settings";
import Organizations from "./pages/Organizations";
import { PrivacyPolicy, TermsOfService } from "./pages/LegalPages";
import Login from "./pages/Login";
import { useAuth } from "./hooks/useAuth";
import "./components/dashboard/SimulationWorkspace.css";
const PAGES = {live: LiveSimulation, "task-summary": TaskSummary, agents: Agents, hiring: Hiring,
  messages: Messages, logs: Logs, replay: Replay, organizations: Organizations, settings: Settings, "recycle-bin": RecycleBin};
function AppContent({ authUser, onSignOut }) {
  const workspace = useWorkspace();
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
      workspace={workspace}
      topbarProps={{
        goal:
          activePage === "hiring"
            ? "Hiring requirements and job descriptions"
            : activePage === "live"
            ? null
            : selectedTask?.directive ??
              "Create a simulation to get started",
        onToggleReplay: () =>
          setActivePage("replay"),
      }}
    >
      {activePage !== "live" && activePage !== "hiring" && (
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

      {error && activePage !== "hiring" && (
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
    <WorkspaceProvider>
      <SimulationProvider>
        <AppContent
          authUser={user}
          onSignOut={signOut}
        />
      </SimulationProvider>
    </WorkspaceProvider>
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
