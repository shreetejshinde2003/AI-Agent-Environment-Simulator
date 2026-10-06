import { useCallback, useEffect, useRef, useState } from "react";
import { useWorkspace } from "../hooks/useWorkspace";
import { useSimulation } from "../context/SimulationContext";
import ConfirmRecycleAction from "../components/common/ConfirmRecycleAction";
import { apiClient } from "../services/apiClient";
import { canManageRecycleBin, canPurgeRecycleBin } from "../utils/recycleBin";

export default function RecycleBin() {
  const { activeWorkspace, activeWorkspaceId } = useWorkspace();
  const { refresh } = useSimulation();
  const [state, setState] = useState({});
  const [busy, setBusy] = useState(false);
  const [pendingPurge, setPendingPurge] = useState(null);
  const generation = useRef(0), mutation = useRef(0);
  const invalidate = useCallback(() => { ++generation.current; ++mutation.current; }, []);
  const allowed = canManageRecycleBin(activeWorkspace);
  const load = useCallback(async () => {
    const token = ++generation.current;
    if (!activeWorkspaceId || !allowed) return;
    setState({workspaceId: activeWorkspaceId, loading: true});
    try {
      const items = await apiClient.getRecycleBin(activeWorkspaceId);
      if (token === generation.current) setState({workspaceId: activeWorkspaceId, items});
    } catch (error) {
      if (token === generation.current) setState({workspaceId: activeWorkspaceId, error: error.message});
    }
  }, [activeWorkspaceId, allowed]);
  useEffect(() => {
    setBusy(false);
    setPendingPurge(null);
    load();
    return invalidate;
  }, [load, invalidate]);
  async function act(item, purge = false) {
    const token = generation.current, operation = ++mutation.current;
    setBusy(true);
    try {
      await (purge ? apiClient.purgeRun : apiClient.restoreRun)(item.id, activeWorkspaceId);
      if (token !== generation.current) return;
      setPendingPurge(null);
      await load();
      await refresh();
    } catch (error) {
      if (token === generation.current) setState(previous => ({...previous, error: error.message}));
    } finally {
      if (operation === mutation.current) setBusy(false);
    }
  }
  const visible = state.workspaceId === activeWorkspaceId ? state : {};
  return <div className="workspace-stack">
    <div className="page-heading"><h1>Recycle Bin</h1>
      {allowed && <button className="text-button" disabled={busy || visible.loading} onClick={load}>Refresh</button>}
    </div>
    <p>Deleted simulations keep their tasks, uploads, and execution evidence. Restore returns the entire run to history. Permanent deletion requires an owner and is blocked for runs with execution evidence.</p>
    {!allowed ? <p role="status">Only workspace owners and organization admins can manage the recycle bin.</p> : <>
      {visible.error && <p role="alert">{visible.error}</p>}
      {visible.loading ? <p role="status">Loading deleted simulations…</p> :
        !visible.items?.length ? <p role="status">The recycle bin is empty.</p> :
          <div className="table-scroll"><table><thead><tr><th>Simulation</th><th>Deleted</th><th>Deleted by</th><th>Last restored</th><th>Actions</th></tr></thead>
            <tbody>{visible.items.map(item => <tr key={item.id}>
              <td>{item.title}<br/><small>{item.id}</small></td>
              <td>{new Date(item.deletedAt).toLocaleString()}</td><td>{item.deletedByUserId}</td>
              <td>{item.restoredAt ? `${new Date(item.restoredAt).toLocaleString()} · ${item.restoredByUserId}` : "—"}</td>
              <td><button className="text-button" disabled={busy} onClick={() => act(item)}>Restore</button>{" "}
                {canPurgeRecycleBin(activeWorkspace) && <button className="text-button" disabled={busy} onClick={() => setPendingPurge({workspaceId: activeWorkspaceId, item})}>Delete permanently</button>}</td>
            </tr>)}</tbody></table></div>}
      {pendingPurge?.workspaceId === activeWorkspaceId && <ConfirmRecycleAction permanent
        title={pendingPurge.item.title} busy={busy} error={visible.error}
        onClose={() => setPendingPurge(null)} onConfirm={() => act(pendingPurge.item, true)}/>}
    </>}
  </div>;
}
