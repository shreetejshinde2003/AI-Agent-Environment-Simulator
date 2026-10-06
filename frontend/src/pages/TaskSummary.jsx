import { useState, useRef } from "react";
import { useWorkspace } from "../hooks/useWorkspace";
import { apiClient } from "../services/apiClient";
import ConfirmRecycleAction from "../components/common/ConfirmRecycleAction";
import { canManageRecycleBin } from "../utils/recycleBin";
import { useSimulation } from "../context/SimulationContext";
import StatsCardRow from "../components/dashboard/StatsCardRow";
import MetricsCharts from "../components/dashboard/MetricsCharts";
import QuickActions from "../components/dashboard/QuickActions";
import { modeLabel, newestRuns, runTitle } from "../utils/runs";
export default function TaskSummary() {
  const {tasks, selectTask, selectedTask, setActivePage, stats, metrics, isLoading, hasLoaded, error, refresh} = useSimulation();
  const { activeWorkspace, activeWorkspaceId } = useWorkspace();
  const currentWorkspace = useRef(activeWorkspaceId);
  currentWorkspace.current = activeWorkspaceId;
  const [operation, setOperation] = useState(null);
  const [pending, setPending] = useState(null);
  const visibleOperation = operation?.workspaceId === activeWorkspaceId ? operation : null;
  async function deleteRun(run) {
    const workspaceId = activeWorkspaceId;
    setOperation({workspaceId, busy: true});
    try {
      await apiClient.deleteRun(run.id, workspaceId);
      if (currentWorkspace.current === workspaceId) {
        setPending(null);
        await refresh();
        setOperation({workspaceId, message: "Simulation moved to the recycle bin."});
      }
    } catch (failure) {
      if (currentWorkspace.current === workspaceId) setOperation({workspaceId, error: failure.message});
    }
  }
  function openRun(id) { selectTask(id); setActivePage("live"); }
  return <div className="workspace-stack">
    <div className="page-heading"><h1>Simulation history</h1><QuickActions/></div>
    {visibleOperation?.error && <p role="alert">{visibleOperation.error}</p>}
    {visibleOperation?.message && <p role="status">{visibleOperation.message}</p>}
    {!tasks.length ? <p className="empty-note" role="status">{isLoading ? "Loading saved simulations…" :
      error ? "Unable to load saved simulations." : "No simulation data yet."}</p> :
      <div className="table-scroll"><table><thead><tr><th>Simulation / goal</th><th>Mode</th><th>Status</th><th>Created</th><th>Duration</th>{canManageRecycleBin(activeWorkspace) && <th>Actions</th>}</tr></thead>
        <tbody>{newestRuns(tasks).map(t => <tr key={t.id} className={t.id === selectedTask?.id ? "selected-row" : ""}>
          <td><button className="text-button" onClick={() => openRun(t.id)}>{runTitle(t)}</button></td>
          <td>{modeLabel(t.executionMode)}</td>
          <td>{t.status.replaceAll("_", " ")}</td><td>{new Date(t.createdAt ?? t.startedAt).toLocaleString()}</td>
          <td>{t.elapsedSeconds == null ? "—" : t.elapsedSeconds.toFixed(2) + "s"}</td>
          {canManageRecycleBin(activeWorkspace) && <td><button className="text-button"
            disabled={visibleOperation?.busy || !["completed", "failed"].includes(t.status)}
            onClick={() => setPending({workspaceId: activeWorkspaceId, run: t})}>Move to bin</button></td>}</tr>)}</tbody>
      </table></div>}
    {pending?.workspaceId === activeWorkspaceId && <ConfirmRecycleAction title={runTitle(pending.run)}
      busy={visibleOperation?.busy} error={visibleOperation?.error}
      onClose={() => setPending(null)} onConfirm={() => deleteRun(pending.run)}/>}
    {hasLoaded && <><StatsCardRow stats={stats}/><MetricsCharts metrics={metrics}/></>}
  </div>;
}
