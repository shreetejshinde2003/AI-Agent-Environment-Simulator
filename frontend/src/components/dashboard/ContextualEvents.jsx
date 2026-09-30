import { useState } from "react";
import { recordMatchesTarget } from "../../utils/eventRecords";

const SOURCES = {all: "All records", event: "Run events", handoff: "Handoffs", activity: "Activity"};
const time = value => value ? new Date(value).toLocaleTimeString() : "Not recorded";

export default function ContextualEvents({task, records, target, selectedKey, onSelect, onShowAll}) {
  const [source, setSource] = useState("all");
  const filtered = records.filter(row => source === "all" || row.source === source);
  const recent = filtered.slice(0, 12);
  // Keep explicit selection reachable if a refresh adds newer records.
  const selected = filtered.find(row => row.key === selectedKey);
  const visible = selected && !recent.includes(selected) ? [...recent.slice(0, 11), selected] : recent;
  return <section className="workbench-events" aria-labelledby="workbench-events-title">
    <div className="workbench-pane-heading"><h2 id="workbench-events-title">Recorded events & handoffs</h2>
      {task && <button type="button" className="text-button" onClick={onShowAll}>View full execution log</button>}</div>
    <div className="event-filters" role="group" aria-label="Record source">
      {Object.entries(SOURCES).map(([value, label]) => <button type="button" key={value}
        aria-pressed={source === value} onClick={() => setSource(value)}>{label}</button>)}
    </div>
    {!visible.length ? <p className="empty-note">{task ? "No recorded entries for this filter yet." : "Choose a run to inspect recorded events."}</p> :
      <ol className="contextual-events" aria-label="Recent recorded entries">{visible.map(row => {
        const current = row.key === selectedKey;
        const related = !current && recordMatchesTarget(task, row, target);
        const {record} = row;
        const failed = row.source === "event" && ["agent_failed", "simulation_failed"].includes(record.type);
        return <li key={row.key} className={[current ? "is-selected" : related ? "is-related" : "", failed ? "is-failure" : ""].filter(Boolean).join(" ")}>
          <button type="button" aria-pressed={current} onClick={() => onSelect(row.key)}
            aria-label={`Inspect ${row.label}, ${time(record.timestamp)}, ${row.source === "handoff" ? `${record.fromAgentId} to ${record.toAgentId}` : record.agentId ?? "run"}${related ? ", related to inspected object" : ""}`}>
            <time dateTime={record.timestamp}>{time(record.timestamp)}</time>
            <span><strong>{row.label}</strong> <small>{SOURCES[row.source]}</small>
              <span className="event-detail">{row.source === "handoff" ? `${record.fromAgentId} → ${record.toAgentId} · ${record.outputKey ?? record.kind}` : record.text}</span>
              {record.agentId && <span className="muted">{record.agentId} · </span>}
              {current ? <span>Selected record</span> : related ? <span>Related to inspected object</span> : null}
            </span>
          </button>
        </li>;
      })}</ol>}
    {task && <p className="muted">Showing {visible.length} of {filtered.length} {source === "all" ? "records" : SOURCES[source].toLowerCase()} · newest first.
      Events, activities and handoffs are distinct saved records. A message event without a message ID cannot identify an exact handoff.</p>}
  </section>;
}
