/**
 * hooks/useBackendConnection.js
 *
 * Polls the backend's /health endpoint on a fixed interval and reports
 * real connection status. This is the ONE source of truth for "is a
 * real backend actually there" — no other file should guess at this.
 *
 * Returns one of: "connecting" | "connected" | "disconnected"
 *   - "connecting": first check hasn't resolved yet
 *   - "connected": last health check succeeded
 *   - "disconnected": last health check failed (backend not running,
 *      wrong URL, CORS misconfigured, network down, etc.)
 */

import { useEffect, useRef, useState } from "react";

// LOCATION-CHANGING: same value as services/apiClient.js's API_BASE_URL —
// must point at wherever backend/app/main.py is actually running.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// USER-DEFINED: how often to re-check. Shorter = detects backend
// coming online faster, but more network chatter. 5s is a reasonable
// default for a dashboard like this.
const POLL_INTERVAL_MS = 5000;

// USER-DEFINED: how long to wait for a health check before giving up
// and treating it as a failure.
const HEALTH_CHECK_TIMEOUT_MS = 3000;

async function checkHealth() {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), HEALTH_CHECK_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      signal: controller.signal,
    });
    return response.ok;
  } catch {
    // Covers: backend not running, wrong URL, CORS block, timeout abort.
    return false;
  } finally {
    clearTimeout(timeoutId);
  }
}

export function useBackendConnection() {
  const [status, setStatus] = useState("connecting");
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;

    async function runCheck() {
      const isHealthy = await checkHealth();
      if (!cancelledRef.current) {
        setStatus(isHealthy ? "connected" : "disconnected");
      }
    }

    runCheck();
    const intervalId = setInterval(runCheck, POLL_INTERVAL_MS);

    return () => {
      cancelledRef.current = true;
      clearInterval(intervalId);
    };
  }, []);

  return status;
}
