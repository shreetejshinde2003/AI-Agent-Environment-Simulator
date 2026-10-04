import { useCallback, useEffect, useMemo, useState } from "react";

import WorkspaceContext from "./WorkspaceContext";
import { workspaceClient } from "../services/workspaceClient";
import { resolveActiveWorkspaceId, workspaceOptions } from "../utils/workspaces";

const STORAGE_KEY = "activeWorkspaceId";

function storedWorkspaceId() {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function persistWorkspaceId(workspaceId) {
  try {
    if (workspaceId) window.localStorage.setItem(STORAGE_KEY, workspaceId);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Selection persistence is a convenience only. Access remains server-authoritative.
  }
}

export default function WorkspaceProvider({ children }) {
  const [workspaceData, setWorkspaceData] = useState(null);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  const refreshWorkspaces = useCallback(async preferredWorkspaceId => {
    setStatus("loading");
    setError(null);
    try {
      const nextData = await workspaceClient.list();
      setWorkspaceData(nextData);
      setActiveWorkspaceId(currentId => {
        const resolved = resolveActiveWorkspaceId(
          nextData,
          preferredWorkspaceId ?? currentId ?? storedWorkspaceId(),
        );
        persistWorkspaceId(resolved);
        return resolved;
      });
      setStatus("ready");
      return nextData;
    } catch (nextError) {
      setError(nextError);
      setStatus("error");
      throw nextError;
    }
  }, []);

  useEffect(() => {
    refreshWorkspaces().catch(() => {});
  }, [refreshWorkspaces]);

  const workspaces = useMemo(
    () => workspaceOptions(workspaceData),
    [workspaceData],
  );

  const activeWorkspace = useMemo(
    () => workspaces.find(workspace => workspace.id === activeWorkspaceId) ?? null,
    [activeWorkspaceId, workspaces],
  );

  const selectWorkspace = useCallback(
    workspaceId => {
      if (!workspaces.some(workspace => workspace.id === workspaceId)) {
        return false;
      }
      setActiveWorkspaceId(workspaceId);
      persistWorkspaceId(workspaceId);
      return true;
    },
    [workspaces],
  );

  const value = useMemo(
    () => ({
      workspaceData,
      workspaces,
      activeWorkspace,
      activeWorkspaceId,
      status,
      error,
      selectWorkspace,
      refreshWorkspaces,
    }),
    [
      workspaceData,
      workspaces,
      activeWorkspace,
      activeWorkspaceId,
      status,
      error,
      selectWorkspace,
      refreshWorkspaces,
    ],
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}
