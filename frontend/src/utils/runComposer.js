export const EXECUTION_STRATEGIES = [
  {value: "single", label: "Single", subtitle: "One agent answers directly", description: "One Direct Agent model call answers the goal using permitted context."},
  {value: "fixed", label: "Fixed", subtitle: "Five specialists in sequence", description: "Research → Data → Analysis → Summarizer → Report."},
  {value: "adaptive", label: "Adaptive", subtitle: "Specialists selected for your task", description: "Rules select specialists using task capabilities and available validated inputs. Only selected specialists execute; routing uses no model call."},
];
export const ADAPTIVE_CATEGORIES = ["summarization", "transformation", "analysis", "reporting", "research_synthesis", "structured_data_analysis", "mixed"];
export const specialistAgents = agents => agents.filter(agent => agent.implemented && !["direct", "orchestrator", "websearch", "web_search"].includes(agent.id));

export function validateRunDraft(draft, agents, datasets) {
  if (!draft.directive.trim()) return "Enter a goal for the simulation.";
  if (draft.directive.length > 10000) return "The goal must be 10,000 characters or fewer.";
  if ((draft.title ?? "").length > 120) return "The title must be 120 characters or fewer.";
  if (!["single", "fixed", "adaptive", "single_agent"].includes(draft.executionMode)) return "Choose an available execution strategy.";
  if (draft.executionMode === "single_agent" && !specialistAgents(agents).some(agent => agent.id === draft.assignedAgentId)) return "Choose an executable specialist.";
  if (draft.datasetId && !datasets?.some(dataset => dataset.active && dataset.datasetId === draft.datasetId)) return "The selected benchmark is unavailable. Choose a registered active dataset or None.";
  if (draft.executionMode === "adaptive" && draft.taskType && !ADAPTIVE_CATEGORIES.includes(draft.taskType)) return "Choose a supported adaptive task category.";
  if ((draft.taskType ?? "").length > 80) return "Task type must be 80 characters or fewer.";
  return null;
}
export function runRequest(draft, uploads) {
  return {directive: draft.directive.trim(), title: draft.title.trim() || null, executionMode: draft.executionMode,
    assignedAgentId: ["fixed", "adaptive"].includes(draft.executionMode) ? "orchestrator" : draft.executionMode === "single" ? "direct" : draft.assignedAgentId,
    uploadIds: draft.executionMode === "single_agent" ? [] : uploads.map(upload => upload.id),
    datasetId: draft.datasetId || null, taskType: draft.taskType.trim() || null};
}
export function validateReferenceFiles(files, attachedCount) {
  if (files.length + attachedCount > 3) return "Maximum three reference files per simulation.";
  for (const file of files) {
    if (!/\.(txt|csv|json)$/i.test(file.name)) return "Reference files must be TXT, CSV or JSON.";
    if (file.size > 262144) return "Each file must be 256 KiB or smaller.";
    if (!file.size) return "Reference files must not be empty.";
  }
  return null;
}
// A synchronous guard closes the gap before React paints disabled controls.
export function createRequestLock() {
  let locked = false;
  return {acquire() { if (locked) return false; locked = true; return true; }, release() { locked = false; }};
}
