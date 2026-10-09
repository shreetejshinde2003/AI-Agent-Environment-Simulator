// Production REST always travels through the browser origin and its API proxy.
export function resolveApiBase(env) {
  return env.DEV ? (env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "") : "";
}
export function resolveSocketUrl(env, browserOrigin) {
  // WebSockets retain their separate transport; REST rewrites do not proxy them.
  const origin = env.VITE_API_BASE_URL || (env.DEV ? "http://localhost:8000" : browserOrigin);
  return env.VITE_WS_URL || origin.replace(/\/$/, "").replace(/^http/, "ws") + "/ws/live";
}
export const API_BASE_URL = resolveApiBase(import.meta.env);
export const WS_URL = resolveSocketUrl(import.meta.env, globalThis.location?.origin);
// REST polling is the default until an authenticated socket topology is approved.
export function liveUpdatesEnabled(env) { return env.VITE_LIVE_UPDATES_ENABLED === "true"; }
export const LIVE_UPDATES_ENABLED = liveUpdatesEnabled(import.meta.env);
