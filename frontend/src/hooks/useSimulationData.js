import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "../services/apiClient";
import { useBackendConnection } from "./useBackendConnection";
import { useLiveSocket } from "./useLiveSocket";
const EMPTY = {agents: [], tasks: [], metrics: {summary: {}, agents: [], history: []}};
export function useSimulationData() {
  const health = useBackendConnection();
  const [data, setData] = useState(EMPTY);
  const [error, setError] = useState(null);
  const busy = useRef(false), pending = useRef(false), mounted = useRef(true);
  const refresh = useCallback(async () => {
    if (busy.current) { pending.current = true; return; }
    busy.current = true;
    do {
      pending.current = false;
      try {
        const [agents, tasks, metrics] = await Promise.all([
          apiClient.getAgents(), apiClient.getTasks(), apiClient.getMetrics()]);
        if (mounted.current) { setData({agents, tasks, metrics}); setError(null); }
      } catch (err) { if (mounted.current) setError(err); }
    } while (pending.current && mounted.current);
    busy.current = false;
  }, []);
  useEffect(() => {
    mounted.current = true;
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => { mounted.current = false; clearInterval(timer); };
  }, [refresh]);
  const socketStatus = useLiveSocket(refresh, health === "connected");
  return {...data, stats: data.metrics.summary, refresh, error, socketStatus,
    connectionStatus: error ? "disconnected" : health, isDemoMode: false,
    isLoading: health === "connecting"};
}
