import {modeLabel, newestRuns, runTitle} from "./runs.js";

export const RUN_PAGE_SIZE = 20;
export const runStatusLabel = status => status?.replaceAll("_", " ") || "Not recorded";
export function runCreatedLabel(run) {
  const value = run.createdAt ?? run.startedAt;
  return value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : "Time not recorded";
}
export function filterRuns(tasks, {query = "", mode = "", status = ""} = {}) {
  const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return newestRuns(tasks).filter(run => {
    const canonicalMode = run.executionMode === "full_pipeline" ? "fixed" : run.executionMode;
    const searchable = `${runTitle(run)} ${run.id} ${modeLabel(run.executionMode)} ${runStatusLabel(run.status)}`.toLowerCase();
    return (!mode || canonicalMode === mode) && (!status || run.status === status) && terms.every(term => searchable.includes(term));
  });
}
// Native buttons retain Tab/Enter/Space semantics; arrows are a convenience,
// not an incomplete ARIA listbox implementation.
export function runNavigationIndex(key, current, count) {
  if (!count) return null;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  if (key === "ArrowDown") return Math.min(current + 1, count - 1);
  if (key === "ArrowUp") return current < 0 ? count - 1 : Math.max(current - 1, 0);
  return null;
}
