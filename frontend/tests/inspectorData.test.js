import test from "node:test";
import assert from "node:assert/strict";
import { canvasPath, stageView } from "../src/utils/graphPresentation.js";
import { graphTarget, resolveInspectorTarget } from "../src/utils/workspaceSelection.js";
import { handoffEvidence, hasAvailableRunContext, recordedTokenCoverage, runEvidence, stageEvidence } from "../src/utils/inspectorData.js";

const stamp = "2026-09-29T10:00:00Z";
const stage = (agentId, status, extra = {}) => ({agentId, status, outputKey: `${agentId}_output`, ...extra});
const message = {id: "m1", fromAgentId: "data", toAgentId: "analysis", outputKey: "structured_data",
  kind: "response", content: "Recorded aggregate only", timestamp: stamp};
const adaptive = {id: "adaptive", executionMode: "adaptive", status: "completed", stages: [
  stage("data", "completed", {startedAt: stamp, totalTokens: 11, model: "test-model", output: "Recorded aggregate only"}),
  stage("analysis", "completed", {startedAt: stamp, totalTokens: 7}),
  stage("report", "completed", {startedAt: stamp, totalTokens: null}),
], messages: [message], events: [{id: "e1", agentId: "analysis", type: "agent_completed", timestamp: stamp, text: "analysis completed"}],
  activities: [{id: "a1", agentId: "analysis", timestamp: stamp, text: "Stage completed"}],
  uploads: [{id: "upload-1", filename: "safe.csv"}], benchmarkContext: "Bounded aggregate context",
  routePlan: {routerVersion: "rules-v1", validationStatus: "valid", selectedAgentIds: ["data", "analysis", "report"],
    skippedAgentIds: ["research", "summarizer"]}};

test("adaptive canvas includes only recorded plan and selected stage rows", () => {
  assert.deepEqual(canvasPath(adaptive), ["goal", "route", "data", "analysis", "report", "result"]);
  assert.deepEqual(graphTarget("route"), {kind: "route"});
  assert.deepEqual(resolveInspectorTarget(adaptive, {runId: "adaptive", target: graphTarget("route")}), {kind: "route"});
  assert.equal(resolveInspectorTarget({...adaptive, routePlan: null}, {runId: "adaptive", target: graphTarget("route")}), null);
  assert.equal(resolveInspectorTarget(adaptive, {runId: "adaptive", target: graphTarget("research")}), null);
});

test("single, fixed, and legacy canvas paths retain their actual distinct topology", () => {
  assert.deepEqual(canvasPath({executionMode: "single", stages: [stage("direct", "completed")]}), ["goal", "direct", "result"]);
  assert.deepEqual(canvasPath({executionMode: "fixed", stages: ["research", "data", "analysis", "summarizer", "report"].map(id => stage(id, "completed"))}),
    ["goal", "orchestrator", "research", "data", "analysis", "summarizer", "report", "result"]);
  assert.deepEqual(canvasPath({executionMode: "single_agent", stages: [stage("research", "completed")]}), ["goal", "research", "result"]);
});

test("stage inspection links only persisted incoming/outgoing handoffs and events", () => {
  const analysis = stageEvidence(adaptive, "analysis");
  assert.deepEqual(analysis.incoming, [message]);
  assert.deepEqual(analysis.outgoing, []);
  assert.equal(analysis.latestEvent.id, "e1");
  assert.equal(analysis.latestActivity.id, "a1");
  assert.deepEqual(stageEvidence(adaptive, "data").outgoing, [message]);
  assert.equal(stageEvidence(adaptive, "research"), null);
  assert.equal(handoffEvidence(adaptive, "m1"), message);
  assert.equal(handoffEvidence(adaptive, "missing"), null);
  assert.equal(handoffEvidence({...adaptive, messages: []}, "m1"), null);
});

test("failed stage preserves its error and only waiting downstream is not executed", () => {
  const failed = {...adaptive, status: "failed", stages: [stage("data", "completed", {startedAt: stamp}),
    stage("analysis", "failed", {startedAt: stamp, error: "Provider unavailable", inputError: {code: "missing_input", missingInputs: ["structured_data"]}}),
    stage("report", "waiting")]};
  const evidence = stageEvidence(failed, "analysis");
  assert.equal(evidence.stage.error, "Provider unavailable");
  assert.deepEqual(evidence.stage.inputError.missingInputs, ["structured_data"]);
  assert.deepEqual(evidence.unstartedDownstream.map(item => item.agentId), ["report"]);
  assert.equal(stageView(failed, failed.stages[2]).text, "Not executed");
  assert.deepEqual(stageEvidence(adaptive, "analysis").unstartedDownstream, []);
});

test("token sum preserves saved measurements even when a legacy start timestamp is absent", () => {
  assert.deepEqual(recordedTokenCoverage(adaptive), {attempted: 3, measured: 2, total: 18});
  assert.deepEqual(recordedTokenCoverage({stages: [stage("research", "completed", {totalTokens: 50})]}),
    {attempted: 0, measured: 1, total: 50});
  assert.deepEqual(recordedTokenCoverage({stages: [stage("research", "waiting", {totalTokens: null})]}),
    {attempted: 0, measured: 0, total: null});
  assert.deepEqual(recordedTokenCoverage(null), {attempted: 0, measured: 0, total: null});
});

test("absent topology is empty and route metadata belongs only to Adaptive", () => {
  assert.deepEqual(canvasPath(null), []);
  assert.deepEqual(canvasPath({executionMode: "fixed"}), []);
  const single = {...adaptive, executionMode: "single", stages: [stage("direct", "completed")]};
  assert.deepEqual(canvasPath(single), ["goal", "direct", "result"]);
  assert.equal(resolveInspectorTarget(single, {runId: single.id, target: {kind: "route"}}), null);
  assert.equal(runEvidence(single).route, null);
  assert.equal(runEvidence(adaptive).route, adaptive.routePlan);
  assert.equal(runEvidence(null), null);
});

test("available reference context does not require or fabricate an incoming message", () => {
  assert.equal(hasAvailableRunContext(adaptive), true);
  assert.equal(hasAvailableRunContext({uploads: [], benchmarkContext: null}), false);
  assert.deepEqual(stageEvidence({...adaptive, messages: []}, "analysis").incoming, []);
  assert.equal(resolveInspectorTarget(adaptive, {runId: "another", target: {kind: "handoff", id: "m1"}}), null);
});
