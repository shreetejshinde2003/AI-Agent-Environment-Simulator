import { graphPath } from "./runs.js";

// Presentation derives from saved run evidence, never from an elapsed-time timer.
export function canvasPath(task) {
  if (!task?.stages?.length) return [];
  const stages = graphPath(task);
  return task.executionMode === "adaptive" && task.routePlan ? [stages[0], "route", ...stages.slice(1)] : stages;
}
export function stageView(task, stage) {
  if (stage.status === "waiting") return ["failed", "completed"].includes(task.status)
    ? {status: "not-executed", text: "Not executed"}
    : {status: "waiting", text: "Selected · waiting"};
  if (stage.status === "active") return {status: "active", text: "Running"};
  if (stage.status === "completed") return {status: "completed", text: "Completed"};
  if (stage.status === "failed") return {status: "failed", text: "Failed"};
  return {status: "waiting", text: "Status unavailable"};
}

export function edgeView(task, from, next, stageMap, message) {
  const actual = message || (from === "goal" && task.executionStartedAt) ||
    (from === "orchestrator" && stageMap[next]?.startedAt) ||
    (from === "goal" && stageMap[next]?.startedAt) ||
    (next === "result" && task.status === "completed");
  // The saved handoff is an instantaneous record, not an in-flight transfer.
  return {recorded: !!actual, animated: false, label: message?.outputKey ?? ""};
}
