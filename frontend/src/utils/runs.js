export const runTitle = task => task.title || task.directive?.replace(/\s+/g, " ").trim().slice(0, 80) || "Untitled simulation";
export const modeLabel = mode => ({single: "Single", fixed: "Fixed", full_pipeline: "Fixed",
  adaptive: "Adaptive · rule-based", single_agent: "Individual specialist"}[mode] ?? mode);
export const newestRuns = tasks => [...tasks].sort((a, b) =>
  (Date.parse(b.createdAt ?? b.startedAt) || 0) - (Date.parse(a.createdAt ?? a.startedAt) || 0) || a.id.localeCompare(b.id));

// No delete API exists. Retain acknowledged records omitted by a stale concurrent
// refresh; never let an earlier event snapshot replace a later one.
export function mergeRuns(incoming, known) {
  const merged = new Map(known.map(task => [task.id, task]));
  for (const task of incoming) {
    const previous = merged.get(task.id);
    if (!previous || (task.events?.length ?? 0) >= (previous.events?.length ?? 0)) merged.set(task.id, task);
  }
  return [...merged.values()];
}
export function graphPath(task) {
  const stages = task?.stages?.map(s => s.agentId) ?? ["research", "data", "analysis", "summarizer", "report"];
  return ["goal", ...(!task || ["fixed", "full_pipeline"].includes(task.executionMode) ? ["orchestrator"] : []), ...stages, "result"];
}
export const workspaceSubtitle = mode => ({
  single: "One goal. One direct baseline agent.",
  fixed: "One goal. Five collaborating specialists. Every handoff visible.",
  adaptive: "One goal. Rule-selected specialists. Every executed handoff visible.",
  single_agent: "One goal. One selected specialist.",
}[mode] ?? "Create a simulation and inspect its real execution.");
export function datasetOptions(datasets) {
  return (datasets ?? []).filter(d => d.active).map(d => ({id: d.datasetId,
    label: `${d.family === "hr" ? "HR" : "Employee"} · ${d.sizeVariant[0].toUpperCase() + d.sizeVariant.slice(1)} · ${d.recordCount} records`}));
}
export const DATASET_EMPTY = "No benchmark datasets are registered on this deployment. The deployment administrator must privately provision and register the benchmark files.";
