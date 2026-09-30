import { graphPath } from "./runs.js";

// UI targets contain identities only. Run content always comes from the latest
// authoritative Task snapshot; switching runs cannot carry an old object over.
export function resolveInspectorTarget(task, selection) {
  if (!task || selection?.runId !== task.id) return null;
  const target = selection.target;
  if (!target) return null;
  if (target.kind === "stage" && task.stages?.some(stage => stage.agentId === target.id)) return target;
  if (target.kind === "handoff" && task.messages?.some(message => message.id === target.id)) return target;
  if (target.kind === "route" && task.executionMode === "adaptive" && task.routePlan) return target;
  if (["goal", "result", "orchestrator"].includes(target.kind) && graphPath(task).includes(target.kind)) return target;
  return null;
}

export function graphTarget(id) {
  if (["goal", "result", "orchestrator", "route"].includes(id)) return {kind: id};
  return {kind: "stage", id};
}

export const hasRecordedTopology = task => !!task?.stages?.length;
export const recentRecordedEvents = (task, limit = 6) => task?.events?.slice(-limit) ?? [];
