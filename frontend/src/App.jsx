import AppShell from "./layout/AppShell";
import RunPicker from "./components/dashboard/RunPicker";
import { SimulationProvider, useSimulation } from "./context/SimulationContext";
import WorkspaceProvider from "./context/WorkspaceProvider";
import { useWorkspace } from "./hooks/useWorkspace";
import LiveSimulation from "./pages/LiveSimulation";
import TaskSummary from "./pages/TaskSummary";
import ResearchLab from "./pages/ResearchLab";
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
import SessionState from "./components/common/SessionState";
import {sessionPresentation} from "./utils/sessionPresentation";
import { useAuth } from "./hooks/useAuth";
import "./components/dashboard/SimulationWorkspace.css";
const PAGES = {research: ResearchLab, live: LiveSimulation, "task-summary": TaskSummary, agents: Agents, hiring: Hiring,
  messages: Messages, logs: Logs, replay: Replay, organizations: Organizations, settings: Settings, "recycle-bin": RecycleBin};
function AppContent({ authUser, onSignOut, signingOut, authError }) {
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
    setExecutionView,
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
    signingOut,
  };

  return (
    <AppShell
      activePage={activePage}
      onNavigate={setActivePage}
      user={user}
      workspace={workspace}
      topbarProps={{
        goal: ["messages", "logs", "replay"].includes(activePage) ? selectedTask?.directive : null,
        onToggleReplay: activePage === "live" && selectedTask ? () => {setExecutionView("events");setActivePage("live");} : null,
      }}
    >
      {authError && <p className="run-error" role="alert">Sign out could not be confirmed. {sessionPresentation(authError).message} Use Sign out to try again.</p>}
      {["messages", "logs", "replay"].includes(activePage) && (
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

      {error && ["task-summary", "agents"].includes(activePage) && (
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
export function WorkspaceBootstrap({children}) {
  const workspace = useWorkspace();
  if (!workspace.activeWorkspaceId || workspace.status === "error") {
    return <SessionState context="workspace" title="Loading your workspaces…"
      description="Preparing workspace access. Your saved selection will open when it is ready."
      error={workspace.error ?? (workspace.status === "ready" ? {status: 404} : null)}
      onRetry={() => workspace.refreshWorkspaces().catch(() => {})}/>;
  }
  return children;
}

function AuthenticatedApp() {
  const {
    user,
    status,
    error,
    signOut,
    signingOut,
    refresh,
  } = useAuth();

  if (status === "loading") {
    return <SessionState title="Checking session…" description="Checking your sign-in before opening your workspace."/>;
  }

  if (
    status === "anonymous" ||
    status === "error" ||
    !user
  ) {
    return <Login error={error} onRetry={refresh} />;
  }

  return (
    <WorkspaceProvider>
      <WorkspaceBootstrap>
        <SimulationProvider>
          <AppContent
            authUser={user}
            onSignOut={signOut}
            signingOut={signingOut}
            authError={error}
          />
        </SimulationProvider>
      </WorkspaceBootstrap>
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
