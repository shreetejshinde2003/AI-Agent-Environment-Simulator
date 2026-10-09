import {
  useCallback,
  useEffect,
  useState,
  useRef,
} from "react";

import {
  getCurrentUser,
  logout as logoutRequest,
} from "../services/authClient";

export function useAuth() {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [signingOut, setSigningOut] = useState(false);
  const generation = useRef(0);
  const logoutBusy = useRef(false);

  const refresh = useCallback(async () => {
    const request = ++generation.current;
    setStatus("loading");
    setError(null);

    try {
      const currentUser = await getCurrentUser();
      if (request !== generation.current) return;

      setUser(currentUser);
      setError(null);
      setStatus(
        currentUser
          ? "authenticated"
          : "anonymous",
      );
    } catch (err) {
      if (request !== generation.current) return;
      setUser(null);
      setError(err);
      setStatus("error");
    }
  }, []);

  const invalidateRefresh = useCallback(() => { ++generation.current; }, []);

  useEffect(() => {
    const params = new URLSearchParams(
      window.location.search,
    );

    if (params.get("auth") === "success") {
      params.delete("auth");

      const query = params.toString();

      window.history.replaceState(
        {},
        "",
        window.location.pathname +
          (query ? `?${query}` : "") +
          window.location.hash,
      );
    }

    function unavailable(event) {
      ++generation.current;
      setUser(null);
      setError(event.detail);
      setStatus("error");
    }
    window.addEventListener("session-unavailable", unavailable);
    refresh();
    return () => {
      invalidateRefresh();
      window.removeEventListener("session-unavailable", unavailable);
    };
  }, [refresh, invalidateRefresh]);

  const signOut = useCallback(async () => {
    if (logoutBusy.current) return;
    logoutBusy.current = true;
    setSigningOut(true);
    setError(null);
    try {
      await logoutRequest();
      ++generation.current;
      setUser(null);
      setStatus("anonymous");
    } catch (err) {
      setError(err);
    } finally {
      logoutBusy.current = false;
      setSigningOut(false);
    }
  }, []);

  return {
    user,
    status,
    error,
    refresh,
    signOut,
    signingOut,
  };
}
