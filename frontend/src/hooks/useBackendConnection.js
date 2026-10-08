import { useEffect, useState } from "react";
import { API_BASE_URL } from "../services/apiConfig";
import { parseApiResponse } from "../services/apiResponse";
export function useBackendConnection() {
  const [status, setStatus] = useState("connecting");
  useEffect(() => {
    let alive = true;
    async function check() {
      try {
        const response = await fetch(API_BASE_URL + "/health", {signal: AbortSignal.timeout(8000)});
        const payload = await parseApiResponse(response, "/health");
        if (alive) setStatus(response.ok && payload?.status === "ok" ? "connected" : "disconnected");
      } catch { if (alive) setStatus("disconnected"); }
    }
    check();
    const timer = setInterval(check, 10000);
    return () => { alive = false; clearInterval(timer); };
  }, []);
  return status;
}
