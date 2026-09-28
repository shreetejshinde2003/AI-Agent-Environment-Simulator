import { useSimulation } from "../context/SimulationContext";
import SimulationDetails from "../components/dashboard/SimulationDetails";
import QuickActions from "../components/dashboard/QuickActions";
export default function TaskSummary() {
  const {tasks, selectTask, selectedTask} = useSimulation();
  return <div className="workspace-stack">
    <div className="page-heading"><h1>Simulation history</h1><QuickActions/></div>
    {!tasks.length ? <p className="empty-note">No simulation data yet.</p> :
      <div className="table-scroll"><table><thead><tr><th>Simulation / goal</th><th>Mode</th><th>Status</th><th>Created</th><th>Duration</th></tr></thead>
        <tbody>{[...tasks].reverse().map(t => <tr key={t.id} className={t.id === selectedTask?.id ? "selected-row" : ""}>
          <td><button className="text-button" onClick={() => selectTask(t.id)}>{t.id} · {t.directive.slice(0, 90)}</button></td>
          <td>{t.executionMode === "single" ? "Single" : ["fixed", "full_pipeline"].includes(t.executionMode) ? "Fixed" : t.executionMode === "single_agent" ? "Individual specialist" : t.executionMode}</td>
          <td>{t.status}</td><td>{new Date(t.createdAt ?? t.startedAt).toLocaleString()}</td>
          <td>{t.elapsedSeconds == null ? "—" : t.elapsedSeconds.toFixed(2) + "s"}</td></tr>)}</tbody>
      </table></div>}
    {selectedTask && <SimulationDetails task={selectedTask}/>}
  </div>;
}
