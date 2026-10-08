import { API_BASE_URL } from "./apiConfig";
import { parseApiResponse } from "./apiResponse";

async function workspaceRequest(path = "", options = {}) {
  const response = await fetch(
    API_BASE_URL + "/api/v1/workspaces" + path,
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

  return parseApiResponse(response, "/api/v1/workspaces" + path);
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
  listOrganizationMembers: workspaceId =>
    workspaceRequest(`/organizations/${encodeURIComponent(workspaceId)}/members`),
  changeOrganizationMemberRole: (workspaceId, userId, membershipRole) =>
    workspaceRequest(
      `/organizations/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(userId)}/role`,
      {
        method: "PATCH",
        body: JSON.stringify({ membershipRole }),
      },
    ),
  removeOrganizationMember: (workspaceId, userId) =>
    workspaceRequest(
      `/organizations/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(userId)}`,
      { method: "DELETE" },
    ),
  listOrganizationHumanRoles: workspaceId =>
    workspaceRequest(`/organizations/${encodeURIComponent(workspaceId)}/human-roles`),
  assignOrganizationHumanRole: (workspaceId, userId, humanRole) =>
    workspaceRequest(
      `/organizations/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(userId)}/human-roles`,
      {
        method: "POST",
        body: JSON.stringify({ humanRole }),
      },
    ),
  deactivateOrganizationHumanRole: (workspaceId, userId, humanRole) =>
    workspaceRequest(
      `/organizations/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(userId)}/human-roles/${encodeURIComponent(humanRole)}`,
      { method: "DELETE" },
    ),
};
