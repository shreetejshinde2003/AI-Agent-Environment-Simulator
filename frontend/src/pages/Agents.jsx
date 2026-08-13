import { useMemo, useState } from "react";
import { useSimulation } from "../context/SimulationContext";
import Card from "../components/common/Card";
import ConnectionBadge from "../components/common/ConnectionBadge";
import "./Agents.css";

/**
 * Agents — full roster grid, built from useSimulation().agents.
 * Each card shows role + live status. Token usage renders once the
 * agent object carries usage data (see getTokenUsage below) — until
 * backend/app/agents/ exposes it, cards just show "No usage data yet".
 */

// ---- defensive field readers -------------------------------------------
// Agent shape isn't finalized yet, so these try a few likely field names
// instead of assuming one and crashing when it's not there.
function getAgentId(agent, fallbackIndex) {
  return agent?.id ?? agent?.agentId ?? agent?.name ?? `agent-${fallbackIndex}`;
}

function getAgentName(agent) {
  return agent?.name ?? agent?.id ?? agent?.agentId ?? "Unnamed Agent";
}

function getAgentRole(agent) {
  return agent?.role ?? agent?.type ?? agent?.title ?? "—";
}

function getAgentStatus(agent) {
  return (agent?.status ?? "unknown").toString().toLowerCase();
}

// ONE-LINE TODO: confirm this matches the real shape once
// backend/app/agents/ exposes per-agent token usage. Currently tries
// agent.tokenUsage, then agent.usage, then agent.tokens.
function getTokenUsage(agent) {
  const u = agent?.tokenUsage ?? agent?.usage ?? agent?.tokens;
  if (u == null) return null;
  if (typeof u === "number") return { total: u, prompt: null, completion: null };
  const total = u.total ?? u.totalTokens ?? null;
  const prompt = u.prompt ?? u.promptTokens ?? null;
  const completion = u.completion ?? u.completionTokens ?? null;
  if (total == null && prompt == null && completion == null) return null;
  return { total, prompt, completion };
}

function initials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  const chars = parts.length > 1 ? parts[0][0] + parts[1][0] : name.slice(0, 2);
  return chars.toUpperCase();
}

const STATUS_LABELS = {
  idle: "Idle",
  active: "Active",
  running: "Running",
  working: "Working",
  busy: "Busy",
  blocked: "Blocked",
  error: "Error",
  failed: "Failed",
  done: "Done",
  completed: "Completed",
  offline: "Offline",
  unknown: "Unknown",
};

export default function Agents() {
  const { agents = [], connectionStatus, isDemoMode } = useSimulation();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const statusOptions = useMemo(() => {
    const set = new Set(agents.map((a) => getAgentStatus(a)));
    return ["all", ...Array.from(set)];
  }, [agents]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return agents.filter((agent) => {
      const name = getAgentName(agent).toLowerCase();
      const role = getAgentRole(agent).toLowerCase();
      const status = getAgentStatus(agent);
      const matchesQuery = !q || name.includes(q) || role.includes(q);
      const matchesStatus = statusFilter === "all" || status === statusFilter;
      return matchesQuery && matchesStatus;
    });
  }, [agents, search, statusFilter]);

  return (
    <div className="agents-page">
      <Card
        title={`Agents (${filtered.length}${
          filtered.length !== agents.length ? ` of ${agents.length}` : ""
        })`}
        headerRight={
          <ConnectionBadge connectionStatus={connectionStatus} isDemoMode={isDemoMode} compact />
        }
      >
        <div className="agents-toolbar">
          <input
            type="text"
            className="agents-search"
            placeholder="Search by name or role…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            className="agents-status-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            {statusOptions.map((s) => (
              <option key={s} value={s}>
                {s === "all" ? "All statuses" : STATUS_LABELS[s] ?? s}
              </option>
            ))}
          </select>
        </div>

        {agents.length === 0 ? (
          <div className="agents-empty">
            No agents yet — they'll appear here once a simulation starts.
          </div>
        ) : filtered.length === 0 ? (
          <div className="agents-empty">No agents match your filters.</div>
        ) : (
          <div className="agents-grid">
            {filtered.map((agent, i) => {
              const id = getAgentId(agent, i);
              const name = getAgentName(agent);
              const role = getAgentRole(agent);
              const status = getAgentStatus(agent);
              const usage = getTokenUsage(agent);

              return (
                <div className="agent-card" key={id}>
                  <div className="agent-card-header">
                    <div className="agent-avatar">{initials(name)}</div>
                    <div className="agent-card-heading">
                      <div className="agent-name">{name}</div>
                      <div className="agent-role">{role}</div>
                    </div>
                    <span className="status-badge" data-status={status}>
                      {STATUS_LABELS[status] ?? status}
                    </span>
                  </div>

                  <div className="agent-card-usage">
                    {usage ? (
                      <>
                        <div className="usage-stat">
                          <span className="usage-label">Prompt</span>
                          <span className="usage-value">{usage.prompt ?? "—"}</span>
                        </div>
                        <div className="usage-stat">
                          <span className="usage-label">Completion</span>
                          <span className="usage-value">{usage.completion ?? "—"}</span>
                        </div>
                        <div className="usage-stat usage-stat-total">
                          <span className="usage-label">Total</span>
                          <span className="usage-value">{usage.total ?? "—"}</span>
                        </div>
                      </>
                    ) : (
                      <div className="usage-empty">No usage data yet</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
