export function validateResearchSample(report) {
  const summary = report?.observedEvidence;
  if (report?.reportVersion !== "research-report-v1" || summary?.configuration?.evidenceKind !== "deterministic_fixture" || !summary.configuration.fixtureSha256 || !Array.isArray(report.runEvidence) || report.runEvidence.length !== 42 || summary.runs?.length !== 42)
    throw new Error("Historical sample provenance could not be verified.");
  const ids = new Set(summary.runs.map(run=>run.taskId));
  if (ids.size !== 42 || report.runEvidence.some(({task})=>!ids.has(task?.id) || task.research?.configuration.evidenceKind !== "deterministic_fixture"))
    throw new Error("Historical sample evidence is incomplete.");
  return report;
}
export async function loadResearchSample(signal) {
  const response = await fetch("/examples/research-fixture-report.json", {signal, credentials: "omit", cache: "no-cache"});
  if (!response.ok) throw new Error("The historical example could not be loaded. Try again.");
  return validateResearchSample(await response.json());
}
export const modeDescriptions = {
  single: "Single · one Direct agent answers the task",
  fixed: "Fixed · all five specialists work in a set sequence",
  adaptive: "Adaptive · selects specialists for the task and records its route",
};
