import { API_BASE_URL } from "./apiClient";
import { apiError } from "../utils/apiErrors";

const WORKSPACE_BASE_URL = import.meta.env.DEV
  ? API_BASE_URL
  : window.location.origin;

async function workspaceRequest(path = "", options = {}) {
  const response = await fetch(
    WORKSPACE_BASE_URL + "/api/v1/workspaces" + path,
    {
      ...options,
      credentials: "include",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...options.headers,
      },
      signal: options.signal ?? AbortSignal.timeout(15000),
    },
  );

  if (!response.ok) {
    let detail;
    try {
      detail = (await response.json()).detail;
    } catch {
      // Preserve a generic message when the backend did not return JSON.
    }
    throw apiError(detail, response.status);
  }

  return response.json();
}

export const workspaceClient = {
  list: () => workspaceRequest(),
  createOrganization: name =>
    workspaceRequest("/organizations", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  joinOrganization: joinCode =>
    workspaceRequest("/organizations/join", {
      method: "POST",
      body: JSON.stringify({ joinCode }),
    }),
};
