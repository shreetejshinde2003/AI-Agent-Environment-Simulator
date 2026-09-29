import { useRef, useState } from "react";
import { modeLabel, newestRuns, runTitle } from "../../utils/runs";

export default function RunPicker({tasks, selectedTask, onSelect}) {
  const [query, setQuery] = useState("");
  const panel = useRef(null), trigger = useRef(null);
  const matching = newestRuns(tasks).filter(t =>
    `${runTitle(t)} ${t.id} ${modeLabel(t.executionMode)} ${t.status}`.toLowerCase().includes(query.toLowerCase()));
  function close() { panel.current.open = false; trigger.current.focus(); }
  return <details className="run-picker" ref={panel} onKeyDown={e => { if (e.key === "Escape") close(); }}>
    <summary ref={trigger}>Simulation · {selectedTask ? runTitle(selectedTask) : "Choose a run"}</summary>
    <div className="run-picker-panel">
      <label htmlFor="run-search">Find a simulation</label>
      <input id="run-search" type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Title, mode, status or ID"/>
      <ul aria-label="Simulation runs">
        {matching.map(t => <li key={t.id}><button type="button" aria-current={t.id === selectedTask?.id ? "true" : undefined}
          onClick={() => { onSelect(t.id); close(); }}>
          <strong>{runTitle(t)}</strong><span>{modeLabel(t.executionMode)} · {t.status.replaceAll("_", " ")}</span>
          <small>{new Date(t.createdAt ?? t.startedAt).toLocaleString()} · {t.id}</small>
        </button></li>)}
      </ul>
      {!matching.length && <p className="muted">{tasks.length ? "No matching runs." : "No simulation data yet."}</p>}
    </div>
  </details>;
}
