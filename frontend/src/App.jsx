import AppShell, { useActivePage } from "./layout/AppShell";
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
  const [activePage, setActivePage] = useActivePage("live");
  const {selectedTask, tasks, selectedTaskId, selectTask, error, socketStatus} = useSimulation();
  const Page = PAGES[activePage] ?? LiveSimulation;
  return <AppShell activePage={activePage} onNavigate={setActivePage}
    user={{name: "Shared workspace", role: "No authentication"}}
    topbarProps={{goal: selectedTask?.directive ?? "Create a simulation to get started",
      onToggleReplay: () => setActivePage("replay")}}>
    <div className="run-toolbar">
      <label htmlFor="selected-run">Simulation</label>
      <select id="selected-run" value={selectedTaskId ?? ""} onChange={e => selectTask(e.target.value)}>
        {!tasks.length && <option value="">No simulation data yet</option>}
        {[...tasks].reverse().map(t => <option value={t.id} key={t.id}>{t.id} · {t.status} · {t.directive.slice(0, 70)}</option>)}
      </select>
      <span className="muted">{socketStatus === "connected" ? "Live events connected" : "Live events offline · REST refresh every 5s"}</span>
    </div>
    {error && <p className="run-error" role="alert">Cannot refresh backend data. Displayed records may be stale. {error.message}</p>}
    <Page />
  </AppShell>;
}
export default function App() {
  return <SimulationProvider><AppContent /></SimulationProvider>;
}
