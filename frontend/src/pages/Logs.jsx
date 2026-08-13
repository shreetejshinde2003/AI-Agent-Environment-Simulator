import { useMemo, useState } from "react";
import { useSimulation } from "../context/SimulationContext";
import Card from "../components/common/Card";
import ConnectionBadge from "../components/common/ConnectionBadge";
import "./Logs.css";

/**
 * Logs — raw timestamped event log.
 *
 * Today this is built by merging `activity` + `messages` from
 * useSimulation(), sorted chronologically — the closest live stand-in
 * for the real thing. Once backend/app/storage/ is persisting
 * broadcast history from backend/app/websocket/manager.py, swap the
 * buildLogEntries() call below for a fetch against that endpoint:
 *
 *   ONE-LINE TODO:
 *   const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/logs`);
 */

function getTimestamp(item) {
  return item?.timestamp ?? item?.time ?? item?.createdAt ?? item?.ts ?? null;
}

function getLabel(item) {
  return (
    item?.message ??
    item?.text ??
    item?.description ??
    item?.content ??
    item?.summary ??
    null
  );
}

function formatTime(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return String(ts);
  return d.toLocaleTimeString(undefined, { hour12: false });
}

function buildLogEntries(activity = [], messages = []) {
  const fromActivity = activity.map((item, i) => ({
    id: item?.id ?? `activity-${i}`,
    timestamp: getTimestamp(item),
    type: item?.type ?? item?.kind ?? "activity",
    label: getLabel(item) ?? "Activity event",
  }));

  const fromMessages = messages.map((item, i) => ({
    id: item?.id ?? `message-${i}`,
    timestamp: getTimestamp(item),
    type: item?.kind ?? item?.type ?? "message",
    label: getLabel(item) ?? "Agent message",
  }));

  return [...fromActivity, ...fromMessages].sort((a, b) => {
    const ta = a.timestamp ? new Date(a.timestamp).getTime() : 0;
    const tb = b.timestamp ? new Date(b.timestamp).getTime() : 0;
    return tb - ta; // newest first
  });
}

export default function Logs() {
  const { activity = [], messages = [], connectionStatus, isDemoMode } = useSimulation();
  const [search, setSearch] = useState("");

  const entries = useMemo(() => buildLogEntries(activity, messages), [activity, messages]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter(
      (e) => e.label.toLowerCase().includes(q) || e.type.toLowerCase().includes(q)
    );
  }, [entries, search]);

  return (
    <div className="logs-page">
      <Card
        title={`Logs (${filtered.length}${
          filtered.length !== entries.length ? ` of ${entries.length}` : ""
        })`}
        headerRight={
          <ConnectionBadge connectionStatus={connectionStatus} isDemoMode={isDemoMode} compact />
        }
      >
        <div className="logs-toolbar">
          <input
            type="text"
            className="logs-search"
            placeholder="Filter events by text or type…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {entries.length === 0 ? (
          <div className="logs-empty">
            No events recorded yet — this fills in as the simulation runs.
          </div>
        ) : filtered.length === 0 ? (
          <div className="logs-empty">No events match your filter.</div>
        ) : (
          <div className="logs-table">
            <div className="logs-row logs-row-head">
              <span className="logs-col-time">Time</span>
              <span className="logs-col-type">Type</span>
              <span className="logs-col-detail">Detail</span>
            </div>
            <div className="logs-body">
              {filtered.map((e) => (
                <div className="logs-row" key={e.id}>
                  <span className="logs-col-time">{formatTime(e.timestamp)}</span>
                  <span className="logs-col-type">
                    <span className="log-type-pill" data-type={e.type}>
                      {e.type}
                    </span>
                  </span>
                  <span className="logs-col-detail">{e.label}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
