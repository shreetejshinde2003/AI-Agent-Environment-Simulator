import { useSimulation } from "../context/SimulationContext";
import SimulationDetails from "../components/dashboard/SimulationDetails";
import Button from "../components/common/Button";
import {sessionPresentation} from "../utils/sessionPresentation";
import QuickActions from "../components/dashboard/QuickActions";
import { modeLabel, runTitle, workspaceSubtitle } from "../utils/runs";
export default function LiveSimulation() {
  const {selectedTask, connectionStatus, isLoading, hasLoaded, error, refresh, lastRefreshedAt, isRefreshing} = useSimulation();
  return <div className="workspace-stack">
    <div className="page-heading workbench-header"><div><p className="workbench-eyebrow">Simulation workspace</p>
      <h1 tabIndex={-1} data-run-heading>{selectedTask ? runTitle(selectedTask) : "Create your first simulation"}</h1>
      <p className="muted">{selectedTask ? workspaceSubtitle(selectedTask.executionMode) : "Select a workspace, describe a task, then follow its execution and read the result."}</p>
      {selectedTask && <p className="workbench-run-meta">{modeLabel(selectedTask.executionMode)} · {selectedTask.status.replaceAll("_", " ")}</p>}
    </div><QuickActions/></div>
    {error && <div className="run-error" role="alert">
      <strong>{sessionPresentation(error).title}</strong><p>{sessionPresentation(error).message}</p>
      {lastRefreshedAt && <p>Showing saved records from {new Date(lastRefreshedAt).toLocaleString()}. They may be out of date.</p>}
      <Button disabled={isRefreshing} onClick={refresh}>{isRefreshing ? "Retrying…" : "Retry loading simulations"}</Button>
    </div>}
    {!error && isLoading && <p className="muted" role="status">Loading saved simulations…</p>}
    {!error && !isLoading && connectionStatus === "disconnected" && <p className="muted" role="status">Connection check unavailable. Saved records are visible; creation is temporarily unavailable.</p>}
    {(hasLoaded || selectedTask) && <SimulationDetails task={selectedTask}/>}
  </div>;
}
