import { useEffect, useState } from "react";
import { API_BASE_URL } from "../services/apiClient";
export function useBackendConnection() {
  const [status, setStatus] = useState("connecting");
  useEffect(() => {
    let alive = true;
    async function check() {
      try {
        const response = await fetch(API_BASE_URL + "/health", {signal: AbortSignal.timeout(8000)});
        if (alive) setStatus(response.ok ? "connected" : "disconnected");
      } catch { if (alive) setStatus("disconnected"); }
    }
    check();
    const timer = setInterval(check, 10000);
    return () => { alive = false; clearInterval(timer); };
  }, []);
  return status;
}
