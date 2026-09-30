import { useSimulation } from "../context/SimulationContext";
import SimulationDetails from "../components/dashboard/SimulationDetails";
import QuickActions from "../components/dashboard/QuickActions";
import { modeLabel, runTitle, workspaceSubtitle } from "../utils/runs";
export default function LiveSimulation() {
  const {selectedTask, connectionStatus, isLoading, hasLoaded} = useSimulation();
  return <div className="workspace-stack">
    <div className="page-heading workbench-header"><div><p className="workbench-eyebrow">Simulation workspace</p>
      <h1 tabIndex={-1} data-run-heading>{selectedTask ? runTitle(selectedTask) : "Choose or create a run"}</h1>
      <p className="muted">{workspaceSubtitle(selectedTask?.executionMode)}</p>
      {selectedTask && <p className="workbench-run-meta">{modeLabel(selectedTask.executionMode)} · {selectedTask.status.replaceAll("_", " ")}</p>}
    </div><QuickActions/></div>
    {connectionStatus === "connecting" && <p className="muted" role="status">Checking backend connection…</p>}
    {connectionStatus === "disconnected" && <p className="run-error" role="alert">Backend unavailable. New runs are disabled; saved records may be stale.</p>}
    {isLoading && <p className="muted" role="status">Loading saved simulations…</p>}
    {(hasLoaded || selectedTask) && <SimulationDetails task={selectedTask}/>}
  </div>;
}
