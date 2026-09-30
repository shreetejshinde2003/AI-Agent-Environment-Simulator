import { useEffect, useId, useMemo, useRef, useState } from "react";
import { modeLabel, runTitle } from "../../utils/runs";
import {filterRuns, RUN_PAGE_SIZE, runCreatedLabel, runNavigationIndex, runStatusLabel} from "../../utils/runBrowser";
import "./RunPicker.css";

export default function RunPicker({tasks, selectedTask, onSelect, isLoading = false, loadError = false}) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState(""), [status, setStatus] = useState("");
  const [limit, setLimit] = useState(RUN_PAGE_SIZE);
  const searchId = useId();
  const panel = useRef(null), trigger = useRef(null), search = useRef(null);
  const matching = useMemo(() => filterRuns(tasks, {query, mode, status}), [tasks, query, mode, status]);
  const visible = matching.slice(0, limit);
  function close() { panel.current.open = false; trigger.current.focus(); }
  function navigate(event) {
    const inSearch = event.target === search.current;
    if (inSearch && !["ArrowDown", "ArrowUp"].includes(event.key)) return;
    if (!inSearch && !event.target.matches("[data-run-choice]")) return;
    const buttons = [...panel.current.querySelectorAll("[data-run-choice]")];
    const index = runNavigationIndex(event.key, buttons.indexOf(event.target), buttons.length);
    if (index !== null) { event.preventDefault(); buttons[index]?.focus(); }
  }
  function filter(setValue, value) { setValue(value); setLimit(RUN_PAGE_SIZE); }
  useEffect(() => {
    function dismiss(event) {
      if (panel.current?.open && !panel.current.contains(event.target)) panel.current.open = false;
    }
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, []);
  return <details className="run-picker" ref={panel}
    onToggle={event => { if (event.currentTarget.open) search.current?.focus(); }}
    onKeyDown={e => { if (e.key === "Escape" && panel.current.open) { e.preventDefault(); close(); } else navigate(e); }}>
    <summary ref={trigger} aria-label={selectedTask ? `Choose run. Current run: ${runTitle(selectedTask)}` : "Choose a run"}>
      <span className="run-picker-caption">{selectedTask ? "Selected run · change" : "Choose a run"}</span>
      <strong className="run-picker-title">{selectedTask ? runTitle(selectedTask) : isLoading ? "Loading runs…" : loadError ? "Runs unavailable" : "No run selected"}</strong>
      {selectedTask && <><span className="run-picker-meta">{modeLabel(selectedTask.executionMode)} · {runStatusLabel(selectedTask.status)}</span>
        <small>{runCreatedLabel(selectedTask)}</small><small className="run-picker-id">ID: {selectedTask.id}</small></>}
    </summary>
    <div className="run-picker-panel">
      <label htmlFor={searchId}>Find a run</label>
      <input ref={search} id={searchId} type="search" value={query} onChange={e => filter(setQuery, e.target.value)} placeholder="Title, mode, status or ID"/>
      <div className="run-picker-filters">
        <div><label htmlFor={`${searchId}-mode`}>Mode</label><select id={`${searchId}-mode`} value={mode} onChange={e => filter(setMode, e.target.value)}>
          <option value="">All modes</option>{["single", "fixed", "adaptive", "single_agent"].map(value => <option key={value} value={value}>{modeLabel(value)}</option>)}
        </select></div>
        <div><label htmlFor={`${searchId}-status`}>Status</label><select id={`${searchId}-status`} value={status} onChange={e => filter(setStatus, e.target.value)}>
          <option value="">All statuses</option>{["queued", "in_progress", "completed", "failed"].map(value => <option key={value} value={value}>{runStatusLabel(value)}</option>)}
        </select></div>
      </div>
      <p className="run-picker-help">Newest first · Tab or arrow keys to browse; Enter to open; Escape to close.</p>
      <ul aria-label="Simulation runs">
        {visible.map(t => <li key={t.id}><button type="button" data-run-choice aria-current={t.id === selectedTask?.id ? "true" : undefined}
          onClick={() => { onSelect(t.id); close(); }}>
          <strong className="run-picker-title">{runTitle(t)}</strong><span>{modeLabel(t.executionMode)} · {runStatusLabel(t.status)}{t.id === selectedTask?.id ? " · Selected" : ""}</span>
          <small>{runCreatedLabel(t)}</small><small className="run-picker-id">ID: {t.id}</small>
        </button></li>)}
      </ul>
      {!!matching.length && <p className="run-picker-help">Showing {visible.length} of {matching.length} matching runs.</p>}
      {matching.length > limit && <button type="button" className="run-picker-more" onClick={() => setLimit(previous => previous + RUN_PAGE_SIZE)}>Show more runs</button>}
      {!matching.length && <p className="muted">{tasks.length ? "No matching runs." : isLoading ?
        "Loading saved simulations…" : loadError ? "Unable to load saved simulations." : "No simulation data yet."}</p>}
    </div>
  </details>;
}
