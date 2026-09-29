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
import "./components/dashboard/SimulationWorkspace.css";
const PAGES = {live: LiveSimulation, "task-summary": TaskSummary, agents: Agents,
  messages: Messages, logs: Logs, replay: Replay, settings: Settings};
function AppContent() {
  const {activePage, setActivePage, selectedTask, tasks, selectTask, error, socketStatus, isLoading, lastRefreshedAt} = useSimulation();
  const Page = PAGES[activePage] ?? LiveSimulation;
  return <AppShell activePage={activePage} onNavigate={setActivePage}
    user={{name: "Shared workspace", role: "No authentication"}}
    topbarProps={{goal: activePage === "live" ? null : selectedTask?.directive ?? "Create a simulation to get started",
      onToggleReplay: () => setActivePage("replay")}}>
    {activePage !== "live" && <div className="run-toolbar">
      <RunPicker tasks={tasks} selectedTask={selectedTask} onSelect={selectTask}
        isLoading={isLoading} loadError={!!error && !tasks.length}/>
      <span className="muted" role="status">{socketStatus === "connected" ? "Live events connected" :
        socketStatus === "connecting" ? "Connecting live events… REST refresh remains available." :
        "Live events offline · REST refresh every 5s"}</span>
    </div>}
    {error && <p className="run-error" role="alert">{lastRefreshedAt ?
      `Cannot refresh backend data. Last successful refresh: ${new Date(lastRefreshedAt).toLocaleString()}. Displayed records may be stale.` :
      "Cannot load backend data."} {error.message}</p>}
    <Page />
  </AppShell>;
}
export default function App() {
  return <SimulationProvider><AppContent /></SimulationProvider>;
}
