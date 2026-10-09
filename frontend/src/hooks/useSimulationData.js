import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "../services/apiClient";
import { useBackendConnection } from "./useBackendConnection";
import { useLiveSocket } from "./useLiveSocket";
import { resolveAcknowledgedRuns } from "../utils/acknowledgedRuns";
import { mergeRuns, mergeActiveRuns } from "../utils/runs";
import { useWorkspace } from "./useWorkspace";
const EMPTY = {agents: [], tasks: [], metrics: {summary: {}, agents: [], history: []}};
export function useSimulationData() {
  const health = useBackendConnection();
  const { activeWorkspaceId, status: workspaceStatus } = useWorkspace();
  const [data, setData] = useState(EMPTY);
  const [error, setError] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState(null);
  const [dataWorkspaceId, setDataWorkspaceId] = useState(null);
  const generation = useRef(0);
  const accepted = useRef(new Map()), revision = useRef(0);
  const busy = useRef(false), pending = useRef(false), mounted = useRef(true);
  const workspaceRef = useRef(activeWorkspaceId);
  workspaceRef.current = activeWorkspaceId;
  const refresh = useCallback(async () => {
    if (!workspaceRef.current) return;
    if (busy.current) { pending.current = true; return; }
    busy.current = true;
    if (mounted.current) setIsRefreshing(true);
    do {
      pending.current = false;
      const workspaceId = workspaceRef.current;
      const requestGeneration = generation.current;
      const refreshRevision = revision.current;
      if (!workspaceId) break;
      try {
        const [agents, listedTasks, metrics] = await Promise.all([
          apiClient.getAgents(workspaceId), apiClient.getTasks(workspaceId), apiClient.getMetrics(workspaceId)]);
        if (!mounted.current || workspaceRef.current !== workspaceId || generation.current !== requestGeneration) continue;
        const acknowledgedIds = [...accepted.current].filter(([, value]) => value <= refreshRevision).map(([id]) => id);
        const tasks = await resolveAcknowledgedRuns(listedTasks, acknowledgedIds, id => apiClient.getTask(id, workspaceId));
        if (mounted.current && workspaceRef.current === workspaceId && generation.current === requestGeneration) {
          // Keep checking omitted acknowledgements until the list catches up or
          // detail confirms removal. Historical list omissions remain authoritative.
          acknowledgedIds.filter(id => listedTasks.some(task => task.id === id) || !tasks.some(task => task.id === id))
            .forEach(id => accepted.current.delete(id));
          setDataWorkspaceId(workspaceId);
          setData(previous => ({agents, tasks: mergeActiveRuns(tasks, previous.tasks,
            [...accepted.current].filter(([, value]) => value > refreshRevision).map(([id]) => id)), metrics}));
          setError(null);
          setHasLoaded(true);
          setLastRefreshedAt(new Date().toISOString());
        }
      } catch (err) {
        if (mounted.current && workspaceRef.current === workspaceId && generation.current === requestGeneration) setError(err);
      }
    } while (pending.current && mounted.current);
    busy.current = false;
    if (mounted.current) setIsRefreshing(false);
  }, []);
  useEffect(() => {
    mounted.current = true;
    ++generation.current;
    setDataWorkspaceId(activeWorkspaceId);
    accepted.current.clear();
    setData(EMPTY);
    setError(null);
    setHasLoaded(false);
    setLastRefreshedAt(null);
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => { mounted.current = false; clearInterval(timer); };
  }, [activeWorkspaceId, refresh]);
  const socketStatus = useLiveSocket(
    refresh,
    health === "connected" && Boolean(activeWorkspaceId),
    activeWorkspaceId,
  );
  const acceptRun = useCallback(run => {
    if (!mounted.current || !workspaceRef.current || run.workspaceId !== workspaceRef.current) return false;
    accepted.current.set(run.id, ++revision.current);
    setDataWorkspaceId(workspaceRef.current);
    setData(previous => ({...previous, tasks: mergeRuns([run], previous.tasks)}));
    return true;
  }, []);
  // Hide the previous tenant during the render before effect cleanup runs.
  const current = dataWorkspaceId === activeWorkspaceId;
  const visible = current ? data : EMPTY;
  const visibleError = current ? error : null;
  const loaded = current && hasLoaded;
  return {...visible, stats: visible.metrics.summary, refresh, acceptRun, error: visibleError, socketStatus,
    hasLoaded: loaded, isRefreshing: current && isRefreshing, lastRefreshedAt: current ? lastRefreshedAt : null,
    backendStatus: health, workspaceStatus,
    connectionStatus: visibleError || workspaceStatus === "error" || health === "disconnected" ? "disconnected" :
      !activeWorkspaceId || !loaded ? "connecting" : health, isDemoMode: false,
    isLoading: !loaded && !visibleError && workspaceStatus !== "error"};
}
