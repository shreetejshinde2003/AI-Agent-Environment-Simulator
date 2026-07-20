/**
 * hooks/useLiveSocket.js
 *
 * STUB — not connected anywhere yet. This is a no-op today; it exists
 * so the "Live" badges scattered around the dashboard have a real
 * data source to attach to once the backend WebSocket
 * (see backend/app/websocket/manager.py) is actually running.
 *
 * When you're ready to go live:
 *   1. Call this hook once, near the top of pages/LiveSimulation.jsx.
 *   2. Have it update SimulationContext state on each incoming event
 *      instead of just logging.
 */

import { useEffect, useRef, useState } from "react";

// LOCATION-CHANGING: must match backend/app/core/config.py's
// WEBSOCKET_PATH, and the host must match VITE_API_BASE_URL's host
// (see services/apiClient.js) but with ws:// instead of http://.
const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/live";

// USER-DEFINED: turn this on once the backend WebSocket endpoint is
// actually running — leaving it off avoids a noisy failed-connection
// error in the console during frontend-only development.
const LIVE_SOCKET_ENABLED = false;

export function useLiveSocket(onEvent) {
  const [isConnected, setIsConnected] = useState(false);
  const socketRef = useRef(null);

  useEffect(() => {
    if (!LIVE_SOCKET_ENABLED) return undefined;

    const socket = new WebSocket(WS_URL);
    socketRef.current = socket;

    socket.onopen = () => setIsConnected(true);
    socket.onclose = () => setIsConnected(false);

    socket.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        // Expected shape: { event: "task_created" | "agent_status_changed" | ..., data: {...}, timestamp }
        onEvent?.(parsed);
      } catch {
        console.warn("Received a non-JSON WebSocket message:", event.data);
      }
    };

    return () => socket.close();
  }, [onEvent]);

  return { isConnected };
}
