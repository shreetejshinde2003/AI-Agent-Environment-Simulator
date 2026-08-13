import { useMemo, useState } from "react";
import { useSimulation } from "../context/SimulationContext";
import MessageFlowFeed from "../components/dashboard/MessageFlowFeed";
import Card from "../components/common/Card";
import ConnectionBadge from "../components/common/ConnectionBadge";
import "./Messages.css";

/**
 * Messages — full agent-to-agent message log. Reuses MessageFlowFeed
 * (same component as the Live Simulation dashboard) with a longer list
 * and a search/filter bar on top: filter by agent, filter by kind
 * (request/response).
 */

// Message field names aren't finalized — these try the common shapes
// so filtering doesn't crash if the schema shifts slightly.
function getMessageAgentIds(msg) {
  return [
    msg?.fromAgentId,
    msg?.toAgentId,
    msg?.senderId,
    msg?.receiverId,
    msg?.agentId,
    msg?.from,
    msg?.to,
  ].filter(Boolean);
}

function getMessageKind(msg) {
  return (msg?.kind ?? msg?.type ?? "unknown").toString().toLowerCase();
}

function getMessageText(msg) {
  return msg?.content ?? msg?.text ?? msg?.message ?? "";
}

function getAgentLabel(agent) {
  return agent?.name ?? agent?.id ?? agent?.agentId ?? "Unknown agent";
}

export default function Messages() {
  const { messages = [], agents = [], connectionStatus, isDemoMode } = useSimulation();
  const [search, setSearch] = useState("");
  const [agentFilter, setAgentFilter] = useState("all");
  const [kindFilter, setKindFilter] = useState("all");

  const kindOptions = useMemo(() => {
    const set = new Set(messages.map((m) => getMessageKind(m)));
    return ["all", ...Array.from(set)];
  }, [messages]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return messages.filter((msg) => {
      const kind = getMessageKind(msg);
      const agentIds = getMessageAgentIds(msg);
      const text = getMessageText(msg).toLowerCase();

      const matchesKind = kindFilter === "all" || kind === kindFilter;
      const matchesAgent = agentFilter === "all" || agentIds.includes(agentFilter);
      const matchesQuery = !q || text.includes(q);

      return matchesKind && matchesAgent && matchesQuery;
    });
  }, [messages, search, agentFilter, kindFilter]);

  return (
    <div className="messages-page">
      <Card
        title={`Messages (${filtered.length}${
          filtered.length !== messages.length ? ` of ${messages.length}` : ""
        })`}
        headerRight={
          <ConnectionBadge connectionStatus={connectionStatus} isDemoMode={isDemoMode} compact />
        }
      >
        <div className="messages-toolbar">
          <input
            type="text"
            className="messages-search"
            placeholder="Search message content…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            className="messages-select"
            value={agentFilter}
            onChange={(e) => setAgentFilter(e.target.value)}
          >
            <option value="all">All agents</option>
            {agents.map((agent, i) => {
              const id = agent?.id ?? agent?.agentId ?? `agent-${i}`;
              return (
                <option key={id} value={id}>
                  {getAgentLabel(agent)}
                </option>
              );
            })}
          </select>
          <select
            className="messages-select"
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value)}
          >
            {kindOptions.map((k) => (
              <option key={k} value={k}>
                {k === "all" ? "All kinds" : k}
              </option>
            ))}
          </select>
        </div>

        {messages.length === 0 ? (
          <div className="messages-empty">
            No messages yet — they'll stream in here once agents start talking.
          </div>
        ) : filtered.length === 0 ? (
          <div className="messages-empty">No messages match your filters.</div>
        ) : (
          <MessageFlowFeed messages={filtered} agents={agents} />
        )}
      </Card>
    </div>
  );
}
