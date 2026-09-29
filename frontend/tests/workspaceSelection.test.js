import test from "node:test";
import assert from "node:assert/strict";
import { graphTarget, hasRecordedTopology, recentRecordedEvents, resolveInspectorTarget } from "../src/utils/workspaceSelection.js";
import { graphPath, mergeRuns } from "../src/utils/runs.js";

const single = {id: "T-single", executionMode: "single", stages: [{agentId: "direct", status: "completed"}],
  messages: [], events: [{id: "s1"}], routePlan: null};
const fixed = {id: "T-fixed", executionMode: "fixed", stages: ["research", "data", "analysis", "summarizer", "report"].map(agentId => ({agentId})),
  messages: [{id: "m1"}], events: [{id: "f1"}], routePlan: null};
const adaptive = {id: "T-adaptive", executionMode: "adaptive", stages: [{agentId: "analysis"}, {agentId: "report"}],
  messages: [{id: "handoff-1"}], events: [{id: "a1"}, {id: "a2"}], routePlan: {selectedAgentIds: ["analysis", "report"], skippedAgentIds: ["research", "data", "summarizer"]}};
const legacy = {id: "T-legacy", executionMode: "single_agent", stages: [{agentId: "data"}], messages: [], events: []};

test("one run ID scopes inspector targets; stale selections and missing objects clear", () => {
  assert.deepEqual(resolveInspectorTarget(adaptive, {runId: adaptive.id, target: graphTarget("analysis")}),
    {kind: "stage", id: "analysis"});
  assert.equal(resolveInspectorTarget(single, {runId: adaptive.id, target: graphTarget("analysis")}), null);
  assert.equal(resolveInspectorTarget(adaptive, {runId: adaptive.id, target: graphTarget("research")}), null);
  assert.equal(resolveInspectorTarget(null, {runId: adaptive.id, target: graphTarget("analysis")}), null);
  assert.deepEqual(resolveInspectorTarget(adaptive, {runId: adaptive.id, target: {kind: "handoff", id: "handoff-1"}}),
    {kind: "handoff", id: "handoff-1"});
  assert.equal(resolveInspectorTarget(adaptive, {runId: adaptive.id, target: {kind: "handoff", id: "missing"}}), null);
});

test("route and coordinator inspection exist only for recorded mode evidence", () => {
  assert.deepEqual(resolveInspectorTarget(adaptive, {runId: adaptive.id, target: {kind: "route"}}), {kind: "route"});
  assert.equal(resolveInspectorTarget(single, {runId: single.id, target: {kind: "route"}}), null);
  assert.deepEqual(resolveInspectorTarget(fixed, {runId: fixed.id, target: graphTarget("orchestrator")}),
    {kind: "orchestrator"});
  assert.equal(resolveInspectorTarget(adaptive, {runId: adaptive.id, target: graphTarget("orchestrator")}), null);
  assert.deepEqual(graphPath(single), ["goal", "direct", "result"]);
  assert.deepEqual(graphPath(fixed), ["goal", "orchestrator", "research", "data", "analysis", "summarizer", "report", "result"]);
  assert.deepEqual(graphPath(adaptive), ["goal", "analysis", "report", "result"]);
  assert.deepEqual(graphPath(legacy), ["goal", "data", "result"]);
});

test("recent events and topology derive only from the selected saved run", () => {
  assert.deepEqual(recentRecordedEvents(adaptive, 1), [{id: "a2"}]);
  assert.deepEqual(recentRecordedEvents(single), [{id: "s1"}]);
  assert.deepEqual(recentRecordedEvents(null), []);
  assert.equal(hasRecordedTopology(adaptive), true);
  assert.equal(hasRecordedTopology({id: "old", stages: []}), false);
  assert.equal(hasRecordedTopology(null), false);
});

test("acknowledged creation and later authoritative refresh retain the active ID", () => {
  const accepted = mergeRuns([adaptive], [fixed]);
  const stale = mergeRuns([fixed], accepted);
  assert.equal(stale.find(run => run.id === adaptive.id), adaptive);
  const refreshed = mergeRuns([{...adaptive, status: "completed", events: [{id: "a1"}, {id: "a2"}, {id: "a3"}]}], stale);
  assert.equal(recentRecordedEvents(refreshed.find(run => run.id === adaptive.id), 1)[0].id, "a3");
});
