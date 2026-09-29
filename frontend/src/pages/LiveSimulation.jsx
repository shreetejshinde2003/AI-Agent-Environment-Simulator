import { useSimulation } from "../context/SimulationContext";
import StatsCardRow from "../components/dashboard/StatsCardRow";
import SimulationDetails from "../components/dashboard/SimulationDetails";
import MetricsCharts from "../components/dashboard/MetricsCharts";
import QuickActions from "../components/dashboard/QuickActions";
import { workspaceSubtitle } from "../utils/runs";
export default function LiveSimulation() {
  const {selectedTask, stats, metrics, connectionStatus} = useSimulation();
  return <div className="workspace-stack">
    <div className="page-heading"><div><h1>Simulation workspace</h1><p className="muted">{workspaceSubtitle(selectedTask?.executionMode)}</p></div><QuickActions/></div>
    {connectionStatus !== "connected" && <p className="run-error">Backend connection unavailable. New runs are disabled; no demo data is substituted.</p>}
    <StatsCardRow stats={stats}/>
    <SimulationDetails task={selectedTask}/>
    <MetricsCharts metrics={metrics}/>
  </div>;
}
