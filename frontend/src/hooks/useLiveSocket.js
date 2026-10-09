import { useEffect, useRef, useState } from "react";
import { WS_URL } from "../services/apiClient";
import { LIVE_UPDATES_ENABLED } from "../services/apiConfig";
export function useLiveSocket(onEvent, enabled = true, workspaceId = null) {
  const callback = useRef(onEvent);
  callback.current = onEvent;
  const [status, setStatus] = useState("disconnected");
  useEffect(() => {
    if (!LIVE_UPDATES_ENABLED) { setStatus("disabled"); return; }
    if (!enabled) { setStatus("disconnected"); return; }
    let socket, timer, disposed = false, retry = 0;
    function connect() {
      setStatus("connecting");
      const url = new URL(WS_URL);
      if (workspaceId) url.searchParams.set("workspaceId", workspaceId);
      socket = new WebSocket(url.toString());
      socket.onopen = () => {
        retry = 0; setStatus("connected");
        callback.current(); // Recover authoritative REST state after every reconnect.
      };
      socket.onmessage = () => callback.current();
      socket.onerror = () => socket.close();
      socket.onclose = () => {
        if (disposed) return;
        setStatus("disconnected");
        timer = setTimeout(connect, Math.min(1000 * 2 ** retry++, 15000));
      };
    }
    connect();
    return () => { disposed = true; clearTimeout(timer); socket?.close(); };
  }, [enabled, workspaceId]);
  return status;
}
