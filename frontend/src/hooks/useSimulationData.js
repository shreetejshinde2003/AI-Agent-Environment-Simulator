/**
 * hooks/useSimulationData.js
 *
 * THE ONE PLACE components get simulation data from.
 *
 * Real behavior (default):
 *   - If the backend isn't reachable, every value is a genuine zero/
 *     empty state. No fabricated numbers, ever. That's the whole fix
 *     this file exists for — a dashboard showing "6/7 agents active"
 *     with no backend running was lying to whoever's looking at it.
 *   - If the backend IS reachable, this fetches real data from it and
 *     polls for updates. (RESERVED: replace the poll with the
 *     WebSocket in hooks/useLiveSocket.js once the backend broadcasts
 *     events — polling is a fine stand-in until then.)
 *
 * Demo mode (opt-in, off by default):
 *   - For UI development/demos without a backend running at all, set
 *     VITE_DEMO_MODE=true in .env, OR append ?demo=true to the URL for
 *     a one-off session. Demo mode is visibly labeled everywhere in
 *     the UI (see components/common/ConnectionBadge.jsx) so it's never
 *     mistaken for real data.
 */

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../services/apiClient";
import { useBackendConnection } from "./useBackendConnection";
import {
  mockAgents,
  mockRelationships,
  mockTasks,
  mockMessages,
  mockActivity,
  mockStats,
  mockTimeline,
} from "../services/mockData";

// --------------------------------------------------------------------
// Honest "nothing is happening" defaults. This is what the dashboard
// shows whenever there's no real backend + real agents behind it.
// --------------------------------------------------------------------
const EMPTY_STATS = {
  simulationId: null,
  status: "offline",
  startTime: null,
  durationSeconds: 0,
  totalAgents: 0,
  activeAgents: 0,
  totalTasks: 0,
  completedTasks: 0,
  totalMessages: 0,
  avgResponseTimeSeconds: 0,
  successRatePercent: 0,
};

const EMPTY_STATE = {
  agents: [],
  relationships: [],
  tasks: [],
  messages: [],
  activity: [],
  stats: EMPTY_STATS,
  timeline: {}, // RESERVED: backend has no timeline endpoint yet — see services/apiClient.js note
};

// USER-DEFINED: how often to re-fetch real data once connected.
const POLL_INTERVAL_MS = 5000;

function isDemoModeEnabled() {
  const envDefault = import.meta.env.VITE_DEMO_MODE === "true"; // USER-DEFINED: default in .env
  if (typeof window === "undefined") return envDefault;

  // Allows overriding per-session without rebuilding, e.g. for a live
  // demo: https://your-app.example.com?demo=true
  const params = new URLSearchParams(window.location.search);
  if (params.get("demo") === "true") return true;
  if (params.get("demo") === "false") return false;
  return envDefault;
}

export function useSimulationData() {
  const isDemoMode = isDemoModeEnabled();
  const connectionStatus = useBackendConnection();
  const [realData, setRealData] = useState(EMPTY_STATE);
  const [error, setError] = useState(null);

  const fetchRealData = useCallback(async () => {
    try {
      const [agents, relationships, tasks, messages, activity, stats] = await Promise.all([
        apiClient.getAgents(),
        apiClient.getAgentRelationships(),
        apiClient.getTasks(),
        apiClient.getMessages(),
        apiClient.getActivityFeed(),
        apiClient.getSimulationStats(),
      ]);
      setRealData({ agents, relationships, tasks, messages, activity, stats, timeline: {} });
      setError(null);
    } catch (err) {
      // A fetch failing mid-session (backend crashed, network drop)
      // should fall back to the honest empty state too, not keep
      // showing stale numbers.
      setError(err);
      setRealData(EMPTY_STATE);
    }
  }, []);

  useEffect(() => {
    if (isDemoMode) return undefined;

    if (connectionStatus !== "connected") {
      setRealData(EMPTY_STATE);
      return undefined;
    }

    fetchRealData();
    const intervalId = setInterval(fetchRealData, POLL_INTERVAL_MS);
    return () => clearInterval(intervalId);
  }, [connectionStatus, isDemoMode, fetchRealData]);

  if (isDemoMode) {
    return {
      agents: mockAgents,
      relationships: mockRelationships,
      tasks: mockTasks,
      messages: mockMessages,
      activity: mockActivity,
      stats: mockStats,
      timeline: mockTimeline,
      connectionStatus: "connected",
      isDemoMode: true,
      isLoading: false,
      error: null,
    };
  }

  return {
    ...realData,
    connectionStatus,
    isDemoMode: false,
    isLoading: connectionStatus === "connecting",
    error,
  };
}
