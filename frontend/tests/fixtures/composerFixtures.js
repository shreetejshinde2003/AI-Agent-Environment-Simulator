import {adaptiveRun, fixedRun, legacyRun, singleRun} from "./inspectorRuns.js";

// Explicit test-only registry metadata; never imported by production components.
export const registeredDatasets = [{datasetId: "fixture-employee-small", active: true,
  name: "Fixture Employee Small", family: "employee", sizeVariant: "small", recordCount: 3},
{datasetId: "fixture-hr-medium", active: true, name: "Fixture HR Medium", family: "hr", sizeVariant: "medium", recordCount: 5},
{datasetId: "fixture-inactive", active: false, family: "hr", sizeVariant: "large", recordCount: 10}];

export function acknowledgedFixture(payload, number) {
  const template = {single: singleRun, fixed: fixedRun, adaptive: adaptiveRun, single_agent: legacyRun}[payload.executionMode];
  const run = structuredClone(template);
  run.id = run.simulationId = `fixture-created-${number}`;
  const title = (payload.title || payload.directive).replace(/\s+/g, " ").trim();
  run.title = title.length <= 80 ? title : title.slice(0, 77).trimEnd() + "…";
  run.directive = payload.directive;
  run.assignedAgentId = payload.assignedAgentId;
  run.createdAt = run.startedAt = "2026-09-30T11:00:00Z";
  run.status = "queued"; run.executionStartedAt = run.completedAt = run.elapsedSeconds = run.output = null;
  run.agentInvocationCount = run.handoffCount = run.progressPercent = 0;
  run.messages = []; run.activities = [];
  run.events = [{id: `${run.id}-created`, type: "simulation_created", timestamp: run.createdAt, text: "Fixture acknowledgement only; no agent executes"}];
  run.stages = run.stages.map(stage => ({...stage, status: "waiting", startedAt: null, completedAt: null,
    durationSeconds: null, model: null, inputTokens: null, outputTokens: null, totalTokens: null, output: null}));
  run.uploads = [];
  run.datasetId = payload.datasetId; run.taskType = payload.taskType;
  // A fixture category/plan is supplied explicitly, not a duplicate router.
  if (run.routePlan) run.routePlan.reasons = ["Fixture plan supplied for UI testing; no routing or execution occurs."];
  return run;
}
export function completedFixture(queued) {
  const run = structuredClone(queued);
  run.status = "completed"; run.progressPercent = 100;
  run.executionStartedAt = "2026-09-30T11:00:01Z"; run.completedAt = "2026-09-30T11:00:03Z";
  run.elapsedSeconds = 2; run.output = "Explicit fixture completion snapshot. No model call was made.";
  run.stages = run.stages.map(stage => ({...stage, status: "completed", startedAt: run.executionStartedAt,
    completedAt: run.completedAt, durationSeconds: null, output: run.output}));
  run.agentInvocationCount = run.stages.length;
  run.events.push({id: `${run.id}-completed`, type: "simulation_completed", timestamp: run.completedAt, text: "Fixture completion snapshot"});
  return run;
}
