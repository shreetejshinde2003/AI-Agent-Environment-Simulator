import { useEffect, useRef, useState } from "react";
import { WS_URL } from "../services/apiClient";
export function useLiveSocket(onEvent, enabled = true) {
  const callback = useRef(onEvent);
  callback.current = onEvent;
  const [status, setStatus] = useState("disconnected");
  useEffect(() => {
    if (!enabled) { setStatus("disconnected"); return; }
    let socket, timer, disposed = false, retry = 0;
    function connect() {
      setStatus("connecting");
      socket = new WebSocket(WS_URL);
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
  }, [enabled]);
  return status;
}
