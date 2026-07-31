/**
 * services/apiClient.js
 *
 * Real backend calls — used by default (see hooks/useSimulationData.js).
 * When the backend isn't reachable, useBackendConnection() reports
 * "disconnected" and this client simply isn't called; the app falls
 * back to genuine zero/empty values instead of guessing.
 *
 * .env setup: copy .env.example to .env and set VITE_API_BASE_URL if
 * your backend runs somewhere other than http://localhost:8000.
 *
 * No component outside hooks/useSimulationData.js should import this
 * file directly — always go through useSimulation().
 *
 * RESERVED: there's no timeline endpoint yet — backend/app/models/schemas.py
 * has no per-agent timing data. SimulationTimeline.jsx will show its
 * empty state until that endpoint exists.
 */

// LOCATION-CHANGING: falls back to the local dev backend if no .env is
// set. Update VITE_API_BASE_URL once the backend is deployed somewhere
// other than your own machine.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API_PREFIX = "/api/v1";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${await response.text()}`);
  }

  return response.json();
}

export const apiClient = {
  getAgents: () => request("/agents"),
  getAgentRelationships: () => request("/agents/relationships"),
  createAgent: (payload) =>
    request("/agents", { method: "POST", body: JSON.stringify(payload) }),

  getTasks: () => request("/tasks"),
  getTask: (id) => request(`/tasks/${id}`),
  createTask: (payload) =>
    request("/tasks", { method: "POST", body: JSON.stringify(payload) }),

  getMessages: (limit = 50) => request(`/messages?limit=${limit}`),

  getSimulationStats: () => request("/simulation/stats"),
  getActivityFeed: (limit = 20) => request(`/simulation/activity?limit=${limit}`),
  pauseSimulation: () => request("/simulation/pause", { method: "POST" }),
  resumeSimulation: () => request("/simulation/resume", { method: "POST" }),
  stopSimulation: () => request("/simulation/stop", { method: "POST" }),
};
