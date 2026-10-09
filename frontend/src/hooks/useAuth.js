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
import { announceSessionChange, setExpectedUser, watchSessionChanges } from "../services/sessionSync";

export function useAuth() {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [signingOut, setSigningOut] = useState(false);
  // Capture before stripping the query so React's repeated effect setup cannot
  // lose callback feedback and silently reopen an existing session.
  const [callbackStatus] = useState(() => new URLSearchParams(window.location.search).get("auth"));
  const generation = useRef(0);
  const logoutBusy = useRef(false);
  const checking = useRef(false);

  const refresh = useCallback(async (quiet = false) => {
    if (quiet === true && (checking.current || logoutBusy.current)) return;
    checking.current = true;
    const request = ++generation.current;
    if (quiet !== true) {
      setStatus("loading");
      setError(null);
    }

    try {
      const currentUser = await getCurrentUser();
      if (request !== generation.current) return;

      setExpectedUser(currentUser);
      setUser(currentUser);
      setError(null);
      setStatus(
        currentUser
          ? "authenticated"
          : "anonymous",
      );
    } catch (err) {
      if (request !== generation.current) return;
      setExpectedUser(null);
      setUser(null);
      setError(err);
      setStatus("error");
    } finally {
      if (request === generation.current) checking.current = false;
    }
  }, []);

  const invalidateRefresh = useCallback(() => { ++generation.current; }, []);

  useEffect(() => {
    const params = new URLSearchParams(
      window.location.search,
    );

    if (callbackStatus === "success" || callbackStatus === "failed") {
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
      checking.current = false;
      setExpectedUser(null);
      setUser(null);
      setError(event.detail);
      setStatus("error");
    }
    window.addEventListener("session-unavailable", unavailable);
    const stopWatching = watchSessionChanges(() => refresh(true));
    if (callbackStatus === "success") announceSessionChange();
    if (callbackStatus === "failed") {
      setExpectedUser(null);
      setStatus("anonymous");
      setError({code: "oauth_sign_in_failed"});
    } else refresh();
    return () => {
      invalidateRefresh();
      checking.current = false;
      stopWatching();
      window.removeEventListener("session-unavailable", unavailable);
    };
  }, [refresh, invalidateRefresh, callbackStatus]);

  const signOut = useCallback(async () => {
    if (logoutBusy.current) return;
    logoutBusy.current = true;
    setSigningOut(true);
    setError(null);
    try {
      await logoutRequest();
      ++generation.current;
      checking.current = false;
      setExpectedUser(null);
      setUser(null);
      setStatus("anonymous");
      announceSessionChange();
    } catch (err) {
      if (err.status === 401) {
        ++generation.current;
        checking.current = false;
        setExpectedUser(null);
        setUser(null);
        setStatus("error");
      }
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
