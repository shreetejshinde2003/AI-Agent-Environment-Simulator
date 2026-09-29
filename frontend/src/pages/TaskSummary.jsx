import { useSimulation } from "../context/SimulationContext";
import StatsCardRow from "../components/dashboard/StatsCardRow";
import MetricsCharts from "../components/dashboard/MetricsCharts";
import QuickActions from "../components/dashboard/QuickActions";
import { modeLabel, newestRuns, runTitle } from "../utils/runs";
export default function TaskSummary() {
  const {tasks, selectTask, selectedTask, setActivePage, stats, metrics, isLoading, hasLoaded, error} = useSimulation();
  function openRun(id) { selectTask(id); setActivePage("live"); }
  return <div className="workspace-stack">
    <div className="page-heading"><h1>Simulation history</h1><QuickActions/></div>
    {!tasks.length ? <p className="empty-note" role="status">{isLoading ? "Loading saved simulations…" :
      error ? "Unable to load saved simulations." : "No simulation data yet."}</p> :
      <div className="table-scroll"><table><thead><tr><th>Simulation / goal</th><th>Mode</th><th>Status</th><th>Created</th><th>Duration</th></tr></thead>
        <tbody>{newestRuns(tasks).map(t => <tr key={t.id} className={t.id === selectedTask?.id ? "selected-row" : ""}>
          <td><button className="text-button" onClick={() => openRun(t.id)}>{runTitle(t)}</button></td>
          <td>{modeLabel(t.executionMode)}</td>
          <td>{t.status.replaceAll("_", " ")}</td><td>{new Date(t.createdAt ?? t.startedAt).toLocaleString()}</td>
          <td>{t.elapsedSeconds == null ? "—" : t.elapsedSeconds.toFixed(2) + "s"}</td></tr>)}</tbody>
      </table></div>}
    {hasLoaded && <><StatsCardRow stats={stats}/><MetricsCharts metrics={metrics}/></>}
  </div>;
}
