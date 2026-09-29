import TaskDetailsPanel from "./TaskDetailsPanel";
import { stageView } from "../../utils/graphPresentation";

const recorded = value => value == null ? "Not recorded" : value;
const time = value => value ? new Date(value).toLocaleString() : "Not recorded";

export default function WorkspaceInspector({task, target, agents = [], onShowRun}) {
  const stage = target?.kind === "stage" ? task?.stages?.find(item => item.agentId === target.id) : null;
  const handoff = target?.kind === "handoff" ? task?.messages?.find(item => item.id === target.id) : null;
  const route = target?.kind === "route" ? task?.routePlan : null;
  const title = stage ? `${agents.find(agent => agent.id === stage.agentId)?.name ?? stage.agentId} · ${stageView(task, stage).text}` :
    handoff ? `${handoff.fromAgentId} → ${handoff.toAgentId}` :
    route ? "Route decision · rule-based" : target?.kind === "goal" ? "User goal" :
      target?.kind === "orchestrator" ? "Sequential coordinator" :
      target?.kind === "result" ? "Final result" : "Run overview";
  return <section className="workbench-inspector" aria-labelledby="workbench-inspector-title">
    <div className="workbench-pane-heading"><h2 id="workbench-inspector-title">Inspector</h2>
      {target && <button type="button" className="text-button" onClick={onShowRun}>Run overview</button>}
    </div>
    <h3 className="workbench-inspector-subtitle">{title}</h3>
    {!task ? <p className="empty-note">Choose a run to inspect its recorded execution.</p> : stage ? <div className="workbench-inspector-content">
      <dl className="metadata">
        <dt>Status</dt><dd>{stageView(task, stage).text}</dd>
        <dt>Output key</dt><dd>{stage.outputKey}</dd>
        <dt>Model</dt><dd>{recorded(stage.model)}</dd>
        <dt>Started</dt><dd>{time(stage.startedAt)}</dd>
        <dt>Completed</dt><dd>{time(stage.completedAt)}</dd>
        <dt>Measured duration</dt><dd>{stage.durationSeconds == null ? "Not recorded" : stage.durationSeconds.toFixed(2) + "s"}</dd>
        <dt>Input tokens</dt><dd>{recorded(stage.inputTokens)}</dd>
        <dt>Output tokens</dt><dd>{recorded(stage.outputTokens)}</dd>
        <dt>Total tokens</dt><dd>{recorded(stage.totalTokens)}</dd>
        <dt>Latest activity</dt><dd>{task.activities?.filter(activity => activity.agentId === stage.agentId).at(-1)?.text ?? "None recorded"}</dd>
      </dl>
      {stage.inputError && <p className="run-error" role="alert">Input contract: {stage.inputError.code}
        {stage.inputError.missingInputs?.length ? ` · Missing ${stage.inputError.missingInputs.join(", ")}` : ""}</p>}
      {stage.error && <p className="run-error" role="alert">{stage.error}</p>}
      <h4>Output</h4><pre>{stage.output ?? "No output recorded."}</pre>
      <p className="muted">Available run context and recorded handoffs are not an exact model-input transcript.</p>
    </div> : handoff ? <div className="workbench-inspector-content">
      <dl className="metadata"><dt>Output key</dt><dd>{recorded(handoff.outputKey)}</dd>
        <dt>Kind</dt><dd>{handoff.kind}</dd><dt>Recorded</dt><dd>{time(handoff.timestamp)}</dd>
        <dt>Characters</dt><dd>{handoff.content.length}</dd><dt>Message ID</dt><dd>{handoff.id}</dd></dl>
      <h4>Handoff content</h4><pre>{handoff.content}</pre>
    </div> : route ? <div className="workbench-inspector-content">
      <dl className="metadata"><dt>Task type</dt><dd>{route.taskType.replaceAll("_", " ")}</dd>
        <dt>Selected</dt><dd>{route.selectedAgentIds.join(" → ")}</dd>
        <dt>Skipped</dt><dd>{route.skippedAgentIds.join(", ") || "None"}</dd>
        <dt>Required capabilities</dt><dd>{route.requiredCapabilities.join(", ") || "None recorded"}</dd>
        <dt>Available inputs</dt><dd>{route.availableInputs.join(", ") || "None recorded"}</dd>
        <dt>Validation</dt><dd>{route.validationStatus}</dd>
        <dt>Router version</dt><dd>{route.routerVersion}</dd></dl>
      <h4>Decision summary</h4><ul>{route.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
      {route.validationError && <p className="run-error">{route.validationError}</p>}
      <p className="muted">This is a recorded rule decision, not a model invocation or private reasoning trace.</p>
    </div> : target?.kind === "goal" ? <p className="directive">{task.directive}</p> :
      target?.kind === "orchestrator" ? <p>The fixed-mode coordinator runs the selected stages in order. It does not invoke a model itself.</p> :
      <TaskDetailsPanel task={task}/>}
  </section>;
}
