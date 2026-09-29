import { useSimulation } from "../context/SimulationContext";
import StatsCardRow from "../components/dashboard/StatsCardRow";
import SimulationDetails from "../components/dashboard/SimulationDetails";
import MetricsCharts from "../components/dashboard/MetricsCharts";
import QuickActions from "../components/dashboard/QuickActions";
import { workspaceSubtitle } from "../utils/runs";
export default function LiveSimulation() {
  const {selectedTask, stats, metrics, connectionStatus, isLoading, hasLoaded} = useSimulation();
  return <div className="workspace-stack">
    <div className="page-heading"><div><h1>Simulation workspace</h1><p className="muted">{workspaceSubtitle(selectedTask?.executionMode)}</p></div><QuickActions/></div>
    {connectionStatus === "connecting" && <p className="muted" role="status">Checking backend connection…</p>}
    {connectionStatus === "disconnected" && <p className="run-error" role="alert">Backend unavailable. New runs are disabled; saved records may be stale.</p>}
    {isLoading && <p className="muted" role="status">Loading saved simulations…</p>}
    {hasLoaded && <><StatsCardRow stats={stats}/>
      <SimulationDetails task={selectedTask}/>
      <MetricsCharts metrics={metrics}/></>}
  </div>;
}
