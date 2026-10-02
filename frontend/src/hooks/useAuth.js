import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  getCurrentUser,
  logout as logoutRequest,
} from "../services/authClient";

export function useAuth() {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    setStatus("loading");

    try {
      const currentUser = await getCurrentUser();

      setUser(currentUser);
      setError(null);
      setStatus(
        currentUser
          ? "authenticated"
          : "anonymous",
      );
    } catch (err) {
      setUser(null);
      setError(err);
      setStatus("error");
    }
  }, []);

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

    refresh();
  }, [refresh]);

  const signOut = useCallback(async () => {
    await logoutRequest();

    setUser(null);
    setError(null);
    setStatus("anonymous");
  }, []);

  return {
    user,
    status,
    error,
    refresh,
    signOut,
  };
}
