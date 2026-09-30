// Relationships use persisted identities/types only. Never parse event prose or
// match timestamps to guess a message ID: message_created does not store one.
const LABELS = {
  simulation_created: "Run queued", simulation_started: "Run started",
  simulation_completed: "Run completed", simulation_failed: "Run failed",
  route_planned: "Route planned", agent_started: "Stage started",
  agent_completed: "Stage completed", agent_failed: "Stage failed",
  message_created: "Message recorded",
};
export function workspaceRecords(task) {
  const rows = [
    ...(task?.events ?? []).map(record => ({source: "event", record,
      label: LABELS[record.type] ?? record.type ?? "Recorded event"})),
    ...(task?.messages ?? []).map(record => ({source: "handoff", record, label: "Agent handoff"})),
    ...(task?.activities ?? []).map(record => ({source: "activity", record, label: "Agent activity"})),
  ];
  return rows.filter(row => row.record.id).map(row => ({...row, key: `${row.source}:${row.record.id}`}))
    .sort((a, b) => (Date.parse(b.record.timestamp) || 0) - (Date.parse(a.record.timestamp) || 0) || a.key.localeCompare(b.key));
}
export function recordTarget(task, row) {
  if (!task || !row) return null;
  const {source, record} = row;
  if (source === "handoff" && task.messages?.some(message => message.id === record.id))
    return {kind: "handoff", id: record.id};
  if (source === "event" && record.type === "route_planned" && task.executionMode === "adaptive" && task.routePlan)
    return {kind: "route"};
  if (source === "event" && ["agent_started", "agent_completed", "agent_failed"].includes(record.type) &&
      task.stages?.some(stage => stage.agentId === record.agentId)) return {kind: "stage", id: record.agentId};
  if (source === "event" && record.type === "simulation_completed" && task.status === "completed") return {kind: "result"};
  if (source === "event" && record.type === "simulation_failed" && task.status === "failed") return {kind: "run"};
  // Activity has a persisted agent ID, but is not a stage lifecycle event.
  // Unlinked events/activities remain independently inspectable.
  return {kind: "event", source, id: record.id};
}
export function recordMatchesTarget(task, row, target) {
  if (!target) return false;
  const related = recordTarget(task, row);
  if (related?.kind === target.kind && related.id === target.id && related.source === target.source) return true;
  return target.kind === "stage" && row.source === "activity" && row.record.agentId === target.id;
}
export function selectedRecord(task, selection, records) {
  return selection?.runId === task?.id ? records.find(row => row.key === selection.recordKey) ?? null : null;
}
