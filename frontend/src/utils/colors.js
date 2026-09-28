/**
 * utils/colors.js
 *
 * Single source of truth for "which color represents which agent role".
 * Every component that draws an agent (graph nodes, timeline rows,
 * avatars, badges) should import from here instead of picking its own
 * color — that's what keeps the whole dashboard visually consistent.
 *
 * These hex values match the CSS variables in src/index.css
 * (--agent-research, --agent-data, etc). If you add a new agent role,
 * add the color in BOTH places.
 */

export const AGENT_ROLE_COLORS = {
  orchestrator: "#8b5cf6",
  research: "#3b82f6",
  data: "#22c55e",
  web_search: "#f59e0b",
  analysis: "#eab308",
  summarizer: "#14b8a6",
  report: "#ec4899",
  direct: "#60a5fa",
};

// USER-DEFINED: fallback color for any role not listed above
// (e.g. a teammate adds a new agent type and forgets to register a color).
export const FALLBACK_AGENT_COLOR = "#94a3b8";

export function colorForRole(role) {
  return AGENT_ROLE_COLORS[role] ?? FALLBACK_AGENT_COLOR;
}

/** Status -> color, used for badges and status dots. */
export const STATUS_COLORS = {
  active: "#22c55e",
  idle: "#64748b",
  waiting: "#f59e0b",
  error: "#ef4444",
  completed: "#22c55e",
  in_progress: "#3b82f6",
  queued: "#64748b",
  failed: "#ef4444",
};

export function colorForStatus(status) {
  return STATUS_COLORS[status] ?? FALLBACK_AGENT_COLOR;
}
