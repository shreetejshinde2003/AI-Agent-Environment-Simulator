import { useState } from "react";
import { apiClient } from "../../services/apiClient";
const date = value => value ? new Date(value).toLocaleString() : "Not yet";
const modeLabel = task => task.executionMode === "single" ? "Single Agent · Direct Baseline" :
  ["fixed", "full_pipeline"].includes(task.executionMode) ? "Fixed five-agent pipeline" :
  task.executionMode === "adaptive" ? "Adaptive · rule-based specialists" :
  task.executionMode === "single_agent" ? `Individual specialist · ${task.assignedAgentId}` :
  task.executionMode;
function ResultText({text}) {
  // Render only simple emphasis as React text. Never interpret model HTML.
  return <div className="final-result result-text">{text.split(/(\*\*[^*\n]+\*\*)/g).map((part, index) =>
    part.startsWith("**") && part.endsWith("**") ?
      <strong key={index}>{part.slice(2, -2)}</strong> : part)}</div>;
}
export default function TaskDetailsPanel({task}) {
  const [error, setError] = useState(null);
  const [exporting, setExporting] = useState(false);
  async function download(format) {
    setExporting(true); setError(null);
    try { await apiClient.exportRun(task.id, format); }
    catch (err) { setError(err.message); }
    finally { setExporting(false); }
  }
  if (!task) return <p className="empty-note">Create a simulation to see real results here.</p>;
  const terminal = ["completed", "failed"].includes(task.status);
  const measured = task.stages.filter(s => s.totalTokens != null);
  return <div className="run-details">
    <span className={"run-status state-" + task.status}>{task.status.replace("_", " ")}</span>
    <p className="directive">{task.directive}</p>
    <dl className="metadata">
      <dt>Simulation ID</dt><dd>{task.id}</dd>
      <dt>Execution</dt><dd>{modeLabel(task)}</dd>
      <dt>Agent invocations</dt><dd>{task.stages.filter(s => s.startedAt).length}</dd>
      <dt>Created</dt><dd>{date(task.createdAt)}</dd>
      <dt>Started</dt><dd>{date(task.executionStartedAt)}</dd>
      <dt>Completed</dt><dd>{date(task.completedAt)}</dd>
      <dt>Duration</dt><dd>{task.elapsedSeconds == null ? "Available after completion" : task.elapsedSeconds.toFixed(2) + "s"}</dd>
      <dt>Tokens</dt><dd>{measured.length ? measured.reduce((sum, s) => sum + s.totalTokens, 0).toLocaleString() : "Not recorded"}</dd>
      <dt>Owner</dt><dd>{task.ownerId ?? "Shared workspace"}</dd>
    </dl>
    {task.routePlan && <section aria-label="Routing trace" className="routing-trace">
      <h3>Rule-based routing · {task.routePlan.routerVersion}</h3>
      <dl className="metadata">
        <dt>Task type</dt><dd>{task.routePlan.taskType.replaceAll("_", " ")}</dd>
        <dt>Selected</dt><dd>{task.routePlan.selectedAgentIds.join(" → ")}</dd>
        <dt>Skipped</dt><dd>{task.routePlan.skippedAgentIds.join(", ") || "None"}</dd>
        <dt>Validation</dt><dd>{task.routePlan.validationStatus}</dd>
        <dt>Handoffs</dt><dd>{task.messages.length}</dd>
      </dl>
      <ul>{task.routePlan.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
      <p className="muted">Selected stages remain waiting until started. Skipped specialists make no calls. This is deterministic routing, not an LLM planner.</p>
    </section>}
    <label>Stages completed: {task.stages.filter(s => s.status === "completed").length} / {task.stages.length}
      <progress max="100" value={task.progressPercent}/></label>
    {task.error && <div className="run-error" role="alert">{task.error}</div>}
    <h3>Final result</h3>
    <ResultText text={task.output ?? (task.status === "failed" ? "No final report. See the failed stage for details." : "No final result yet.")}/>
    {!!task.uploads?.length && <section><h3>Uploaded context</h3>{task.uploads.map(u =>
      <details key={u.id}><summary>{u.filename} · {u.sizeBytes} bytes{u.truncated ? " · Truncated for context" : ""}</summary>
        <p>{u.rowCount != null ? u.rowCount + " rows · " + u.columns.length + " columns" : u.format.toUpperCase()}</p><pre>{u.preview}</pre></details>)}</section>}
    <div className="export-controls">{["txt", "json", "csv"].map(format =>
      <button key={format} disabled={!terminal || exporting} onClick={() => download(format)}>Export {format.toUpperCase()}</button>)}</div>
    {error && <p role="alert" className="run-error">{error}</p>}
  </div>;
}
