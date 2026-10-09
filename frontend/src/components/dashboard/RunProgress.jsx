import {runStatusLabel} from "../../utils/runBrowser";

// All progress comes from the current persisted run snapshot, never a timer.
export default function RunProgress({task, agents = [], onInspect}) {
  if (!task) return null;
  const stages = task.stages ?? [];
  const completed = stages.filter(stage => stage.status === "completed").length;
  const failed = stages.filter(stage => stage.status === "failed");
  const running = stages.filter(stage => ["active", "running", "in_progress"].includes(stage.status));
  const planned = stages.filter(stage => stage.status !== "skipped");
  const agentName = stage => agents.find(agent => agent.id === stage.agentId)?.name ?? stage.agentId;
  return <section className={`run-progress state-${task.status}`} aria-label="Run progress">
    <p role="status"><strong>{runStatusLabel(task.status)}</strong> · {task.status === "completed" ?
      task.output != null ? "Final answer available below." : "Execution finished; no final answer was recorded." :
      task.status === "failed" ? "Execution stopped. Review the recorded evidence before creating another simulation." :
      task.status === "queued" ? "Waiting to start. Updates appear automatically." :
      running.length ? `Working: ${running.map(agentName).join(", ")}.` : "Waiting for the next recorded update."}</p>
    {!!stages.length && <p className="muted">{completed} of {planned.length} recorded stages completed{stages.length > planned.length ? ` · ${stages.length - planned.length} skipped` : ""}.</p>}
    {task.status === "failed" && <>
      <details><summary>Recorded failure</summary><p className="output-text">{task.error || "No failure message was recorded."}</p></details>
      {failed.map(stage => <button type="button" className="text-button" key={stage.agentId}
        onClick={() => onInspect({kind: "stage", id: stage.agentId})}>Review failed stage: {agentName(stage)}</button>)}
      {!failed.length && <button type="button" className="text-button" onClick={() => onInspect(null)}>Review run evidence</button>}
    </>}
  </section>;
}
