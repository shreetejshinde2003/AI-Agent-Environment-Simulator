// One environment-aware origin for REST, health and WebSocket traffic.
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? "http://localhost:8000" : window.location.origin)).replace(/\/$/, "");
export const WS_URL = import.meta.env.VITE_WS_URL ||
  API_BASE_URL.replace(/^http/, "ws") + "/ws/live";
async function request(path, options = {}) {
  const response = await fetch(API_BASE_URL + "/api/v1" + path, {
    ...options, headers: { "Content-Type": "application/json", ...options.headers },
    signal: options.signal ?? AbortSignal.timeout(15000),
  });
  if (!response.ok) {
    let detail;
    try { detail = (await response.json()).detail; } catch { /* generic safe error */ }
    throw new Error(typeof detail === "string" ? detail : detail?.message || "Request failed (" + response.status + ")");
  }
  return response.json();
}
export const apiClient = {
  getAgents: () => request("/agents"),
  getAgentRelationships: () => request("/agents/relationships"),
  createAgent: payload => request("/agents", {method: "POST", body: JSON.stringify(payload)}),
  getTasks: () => request("/tasks"),
  getTask: id => request("/tasks/" + encodeURIComponent(id)),
  getDatasets: () => request("/datasets"),
  createTask: payload => request("/tasks", {method: "POST", body: JSON.stringify(payload)}),
  getMetrics: () => request("/simulations/metrics"),
  getMessages: (limit = 50) => request("/messages?limit=" + limit),
  getSimulationStats: () => request("/simulation/stats"),
  getActivityFeed: (limit = 20) => request("/simulation/activity?limit=" + limit),
  upload: file => request("/uploads?filename=" + encodeURIComponent(file.name),
    {method: "POST", body: file, headers: {"Content-Type": file.type || "application/octet-stream"}}),
  async exportRun(id, format) {
    const response = await fetch(API_BASE_URL + "/api/v1/simulations/" + encodeURIComponent(id) +
      "/export?format=" + format, {signal: AbortSignal.timeout(15000)});
    if (!response.ok) throw new Error("Export unavailable (" + response.status + ")");
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url; link.download = id + "." + format;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};
