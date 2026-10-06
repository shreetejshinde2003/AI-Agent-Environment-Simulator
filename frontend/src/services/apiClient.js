import {apiError, creationError} from "../utils/apiErrors";
// One environment-aware origin for REST, health and WebSocket traffic.
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? "http://localhost:8000" : window.location.origin)).replace(/\/$/, "");
export const WS_URL = import.meta.env.VITE_WS_URL ||
  API_BASE_URL.replace(/^http/, "ws") + "/ws/live";
function workspaceHeaders(workspaceId) {
  return workspaceId ? {"X-Workspace-Id": workspaceId} : {};
}
async function request(path, options = {}) {
  const response = await fetch(API_BASE_URL + "/api/v1" + path, {
    ...options,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options.headers },
    signal: options.signal ?? AbortSignal.timeout(15000),
  });
  if (!response.ok) {
    let detail;
    try { detail = (await response.json()).detail; } catch { /* generic safe error */ }
    throw apiError(detail, response.status);
  }
  return response.json();
}
export const apiClient = {
  getAgents: () => request("/agents"),
  getAgentRelationships: () => request("/agents/relationships"),
  createAgent: payload => request("/agents", {method: "POST", body: JSON.stringify(payload)}),
  getTasks: workspaceId => request("/tasks", {headers: workspaceHeaders(workspaceId)}),
  getTask: (id, workspaceId) => request("/tasks/" + encodeURIComponent(id), {headers: workspaceHeaders(workspaceId)}),
  getRecycleBin: workspaceId => request("/recycle-bin", {headers: workspaceHeaders(workspaceId)}),
  deleteRun: (id, workspaceId) => request("/simulations/" + encodeURIComponent(id),
    {method: "DELETE", headers: workspaceHeaders(workspaceId)}),
  restoreRun: (id, workspaceId) => request("/recycle-bin/simulations/" + encodeURIComponent(id) + "/restore",
    {method: "POST", headers: workspaceHeaders(workspaceId)}),
  purgeRun: (id, workspaceId) => request("/recycle-bin/simulations/" + encodeURIComponent(id),
    {method: "DELETE", body: JSON.stringify({confirmPermanentDeletion: true}), headers: workspaceHeaders(workspaceId)}),
  getDatasets: () => request("/datasets"),
  createTask: (payload, workspaceId) => request("/tasks", {method: "POST", body: JSON.stringify(payload), headers: workspaceHeaders(workspaceId)}).catch(error => {throw creationError(error);}),
  getMetrics: workspaceId => request("/simulations/metrics", {headers: workspaceHeaders(workspaceId)}),
  getMessages: (limit = 50, workspaceId) => request("/messages?limit=" + limit, {headers: workspaceHeaders(workspaceId)}),
  getSimulationStats: workspaceId => request("/simulation/stats", {headers: workspaceHeaders(workspaceId)}),
  getActivityFeed: (limit = 20, workspaceId) => request("/simulation/activity?limit=" + limit, {headers: workspaceHeaders(workspaceId)}),
  upload: (file, workspaceId) => request("/uploads?filename=" + encodeURIComponent(file.name),
    {method: "POST", body: file, headers: {...workspaceHeaders(workspaceId),
      "Content-Type": file.type || "application/octet-stream"}}),
  async exportRun(id, format, workspaceId) {
    const response = await fetch(API_BASE_URL + "/api/v1/simulations/" + encodeURIComponent(id) +
      "/export?format=" + format, {credentials: "include", headers: workspaceHeaders(workspaceId), signal: AbortSignal.timeout(15000)});
    if (!response.ok) throw new Error("Export unavailable (" + response.status + ")");
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url; link.download = id + "." + format;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};
