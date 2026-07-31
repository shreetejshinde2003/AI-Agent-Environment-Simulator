/**
 * hooks/useLiveSocket.js
 *
 * Connects to the backend's WebSocket broadcast
 * (backend/app/websocket/manager.py) and fires `onEvent` for every
 * message. Used by hooks/useSimulationData.js to refetch immediately
 * when something actually changes, instead of waiting for the next
 * 5-second poll.
 */

import { useEffect, useRef, useState } from "react";

// LOCATION-CHANGING: must match backend/app/core/config.py's
// WEBSOCKET_PATH, and the host must match VITE_API_BASE_URL's host
// (see services/apiClient.js) but with ws:// instead of http://.
const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/live";

// USER-DEFINED: global kill-switch, independent of the `enabled` param
// below. Turn off only if you need to debug polling in isolation.
const LIVE_SOCKET_ENABLED = true;

/**
 * @param onEvent  called with the parsed { event, data, timestamp } message
 * @param enabled  per-call gate — e.g. useSimulationData only passes
 *                 true once connectionStatus === "connected", so this
 *                 doesn't try to open a socket against a backend that
 *                 isn't there.
 */
export function useLiveSocket(onEvent, enabled = true) {
  const [isConnected, setIsConnected] = useState(false);
  const socketRef = useRef(null);

  useEffect(() => {
    if (!LIVE_SOCKET_ENABLED || !enabled) return undefined;

    const socket = new WebSocket(WS_URL);
    socketRef.current = socket;

    socket.onopen = () => setIsConnected(true);
    socket.onclose = () => setIsConnected(false);
    socket.onerror = () => setIsConnected(false);

    socket.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        // Real shape, from backend/app/websocket/manager.py's broadcast():
        // { event: "task_created" | "task_updated" | "agent_status_changed" |
        //   "activity_event" | "message_sent" | "stats_updated", data: {...}, timestamp }
        onEvent?.(parsed);
      } catch {
        console.warn("Received a non-JSON WebSocket message:", event.data);
      }
    };

    return () => socket.close();
  }, [onEvent, enabled]);

  return { isConnected };
}
