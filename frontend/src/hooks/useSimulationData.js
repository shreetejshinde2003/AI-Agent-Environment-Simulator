import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "../services/apiClient";
import { useBackendConnection } from "./useBackendConnection";
import { useLiveSocket } from "./useLiveSocket";
import { mergeRuns } from "../utils/runs";
import { useWorkspace } from "./useWorkspace";
const EMPTY = {agents: [], tasks: [], metrics: {summary: {}, agents: [], history: []}};
export function useSimulationData() {
  const health = useBackendConnection();
  const { activeWorkspaceId } = useWorkspace();
  const [data, setData] = useState(EMPTY);
  const [error, setError] = useState(null);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState(null);
  const busy = useRef(false), pending = useRef(false), mounted = useRef(true);
  const workspaceRef = useRef(activeWorkspaceId);
  workspaceRef.current = activeWorkspaceId;
  const refresh = useCallback(async () => {
    if (!workspaceRef.current) return;
    if (busy.current) { pending.current = true; return; }
    busy.current = true;
    do {
      pending.current = false;
      const workspaceId = workspaceRef.current;
      if (!workspaceId) break;
      try {
        const [agents, tasks, metrics] = await Promise.all([
          apiClient.getAgents(), apiClient.getTasks(workspaceId), apiClient.getMetrics(workspaceId)]);
        if (mounted.current && workspaceRef.current === workspaceId) {
          setData(previous => ({agents, tasks: mergeRuns(tasks, previous.tasks), metrics}));
          setError(null);
          setHasLoaded(true);
          setLastRefreshedAt(new Date().toISOString());
        }
      } catch (err) {
        if (mounted.current && workspaceRef.current === workspaceId) setError(err);
      }
    } while (pending.current && mounted.current);
    busy.current = false;
  }, []);
  useEffect(() => {
    mounted.current = true;
    setData(EMPTY);
    setError(null);
    setHasLoaded(false);
    setLastRefreshedAt(null);
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => { mounted.current = false; clearInterval(timer); };
  }, [activeWorkspaceId, refresh]);
  const socketStatus = useLiveSocket(refresh, health === "connected");
  const acceptRun = useCallback(run => setData(previous => ({...previous, tasks: mergeRuns([run], previous.tasks)})), []);
  return {...data, stats: data.metrics.summary, refresh, acceptRun, error, socketStatus, hasLoaded, lastRefreshedAt,
    connectionStatus: error ? "disconnected" : health, isDemoMode: false,
    isLoading: !hasLoaded && !error};
}
