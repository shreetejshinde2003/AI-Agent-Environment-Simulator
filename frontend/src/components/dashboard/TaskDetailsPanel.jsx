import { useState } from "react";
import { apiClient } from "../../services/apiClient";
import RecordedText from "./RecordedText";
import OutputViewer from "./OutputViewer";
import { runEvidence } from "../../utils/inspectorData";
import { runTitle } from "../../utils/runs";
const date = value => value ? new Date(value).toLocaleString() : "Not recorded";
const duration = value => value == null ? "Not recorded" : `${value.toFixed(2)}s`;
const modeLabel = task => task.executionMode === "single" ? "Single Agent · Direct Baseline" :
  ["fixed", "full_pipeline"].includes(task.executionMode) ? "Fixed five-agent pipeline" :
  task.executionMode === "adaptive" ? "Adaptive · rule-based specialists" :
  task.executionMode === "single_agent" ? `Individual specialist · ${task.assignedAgentId}` :
  task.executionMode;
export default function TaskDetailsPanel({task, view = "overview", onInspect}) {
  const [error, setError] = useState(null);
  const [exporting, setExporting] = useState(false);
  async function download(format) {
    setExporting(true); setError(null);
    try { await apiClient.exportRun(task.id, format, task.workspaceId); }
    catch (err) { setError(err.message); }
    finally { setExporting(false); }
  }
  if (!task) return <p className="empty-note">Create a simulation to see real results here.</p>;
  const {stages, models, tokens, invocationCount, handoffCount, startedAgentIds, route, terminal, finalStage} = runEvidence(task);
  return <div className="run-details">
    <span className={"run-status state-" + task.status}>{task.status.replace("_", " ")}</span>
    <h4 className="run-inspector-title">{runTitle(task)}</h4>
    {view === "overview" && <p className="directive">{task.directive}</p>}
    <dl className="metadata">
      <dt>Simulation ID</dt><dd><code>{task.id}</code></dd>
      <dt>Execution</dt><dd>{modeLabel(task)}</dd>
      <dt>Stage attempts</dt><dd>{invocationCount}</dd>
      <dt>Handoffs</dt><dd>{handoffCount}</dd>
      {view === "overview" && <>
      {models.length > 0 && <><dt>Recorded models</dt><dd>{models.map(model => <code key={model}>{model} </code>)}</dd></>}
      {task.taskType && <><dt>Task type</dt><dd>{task.taskType.replaceAll("_", " ")}</dd></>}
      {task.datasetId && <><dt>Benchmark dataset</dt><dd><code>{task.datasetId}</code></dd></>}
      {task.datasetChecksum && <><dt>Dataset checksum</dt><dd><code>{task.datasetChecksum}</code></dd></>}
      <dt>Created</dt><dd>{date(task.createdAt)}</dd>
      <dt>Started</dt><dd>{date(task.executionStartedAt)}</dd>
      </>}
      <dt>Completed</dt><dd>{date(task.completedAt)}</dd>
      <dt>Measured duration</dt><dd>{duration(task.elapsedSeconds)}</dd>
      <dt>Recorded tokens</dt><dd>{tokens.total == null ? "Not recorded" : tokens.total.toLocaleString()}</dd>
      {stages.length > 0 && <><dt>Token coverage</dt><dd>{tokens.measured} of {stages.length} stage records</dd></>}
      {view === "overview" && <><dt>Workspace</dt><dd><code>{task.workspaceId ?? "Not recorded"}</code></dd></>}
    </dl>
    {view === "overview" && <>
    {task.executionMode === "single" && <p className="muted">One direct-answer baseline agent; no specialist handoffs or route decision.</p>}
    {["fixed", "full_pipeline"].includes(task.executionMode) && <p className="muted">Fixed five-specialist sequence. No adaptive route decision was made.</p>}
    {task.executionMode === "single_agent" && <p className="muted">Individual specialist utility run: {task.assignedAgentId}. Not a three-mode research comparison run.</p>}
    {stages.length > 0 && <section aria-label="Recorded execution path"><h4>Recorded stage starts</h4>
      <p className="muted">{startedAgentIds.length ? startedAgentIds.join(" → ") : "No stage start recorded."}</p></section>}
    {route && <section aria-label="Routing trace" className="routing-trace">
      <h4>Rule-based routing · {route.routerVersion}</h4>
      <dl className="metadata">
        <dt>Task type</dt><dd>{route.taskType?.replaceAll("_", " ") ?? "Not recorded"}</dd>
        <dt>Selected</dt><dd>{route.selectedAgentIds?.join(" → ") || "None recorded"}</dd>
        <dt>Skipped</dt><dd>{route.skippedAgentIds?.join(", ") || "None"}</dd>
        <dt>Validation</dt><dd>{route.validationStatus ?? "Not recorded"}</dd>
      </dl>
      {route.reasons?.length > 0 && <ul>{route.reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul>}
      {route.validationError && <p className="run-error">{route.validationError}</p>}
      <p className="muted">Selected stages remain waiting until started. Skipped specialists make no calls. This is deterministic routing, not an LLM planner.</p>
    </section>}
    {stages.length > 0 && <label>Stages completed: {stages.filter(s => s.status === "completed").length} / {stages.length}
      <progress max="100" value={task.progressPercent}/></label>}
    {task.error && <div className="run-error" role="alert">{task.error}</div>}
    {task.status === "failed" && onInspect && stages.filter(stage => stage.status === "failed").map(stage =>
      <button key={stage.agentId} type="button" className="text-button" onClick={() => onInspect?.({kind: "stage", id: stage.agentId})}>
        Inspect failed stage: {stage.agentId}
      </button>)}
    </>}
    {view !== "metadata" && <><h4>{view === "result" ? "Recorded final output" : "Final result"}</h4>
    {view === "result" && task.output != null && <dl className="metadata">
      {task.output != null && <><dt>Characters</dt><dd>{task.output.length.toLocaleString()}</dd>
        {finalStage?.status === "completed" && finalStage.output === task.output && <><dt>Recorded source</dt><dd>{finalStage.agentId} · <code>{finalStage.outputKey}</code></dd></>}</>}
    </dl>}
    {task.output == null ? <p className="empty-note">{task.status === "failed" ? "No final result. See the failed stage for partial output and error details." : "No final result yet."}</p> :
      <OutputViewer text={task.output} directive={task.directive} contract={finalStage?.outputContract} label="Final answer"/>}</>}
    {view === "overview" && !!task.uploads?.length && <section><h4>Uploaded context</h4>{task.uploads.map(u =>
      <details key={u.id}><summary>{u.filename} · {u.sizeBytes} bytes{u.truncated ? " · Truncated for context" : ""}</summary>
        <p>{u.rowCount != null ? `${u.rowCount} rows${u.columns ? ` · ${u.columns.length} columns` : ""}` : u.format?.toUpperCase()}</p><RecordedText text={u.preview} label="upload preview"/></details>)}</section>}
    {view === "overview" && task.benchmarkContext && <details><summary>Prepared benchmark context</summary>
      <p className="muted">Saved bounded aggregate context; raw benchmark rows are not included.</p>
      <RecordedText text={task.benchmarkContext} label="benchmark context"/></details>}
    <div className="export-controls">{["txt", "json", "csv"].map(format =>
      <button key={format} disabled={!terminal || exporting} onClick={() => download(format)}>Export {format.toUpperCase()}</button>)}</div>
    {error && <p role="alert" className="run-error">{error}</p>}
  </div>;
}
