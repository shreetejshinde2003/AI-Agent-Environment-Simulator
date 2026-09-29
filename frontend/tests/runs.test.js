import test from "node:test";
import assert from "node:assert/strict";
import { mergeRuns, newestRuns, runTitle, graphPath, workspaceSubtitle, datasetOptions, DATASET_EMPTY } from "../src/utils/runs.js";

const old = {id: "T-old", directive: "Old goal", executionMode: "fixed", createdAt: "2026-09-01", events: [1, 2, 3]};
const created = {id: "T-new", title: "New goal", executionMode: "adaptive", createdAt: "2026-09-29", events: [1, 2]};
test("new server-acknowledged run remains selectable during stale refresh and WS updates", () => {
  const accepted = mergeRuns([created], [old]);
  const staleRefresh = mergeRuns([old], accepted);
  assert.equal(staleRefresh.find(t => t.id === created.id).title, "New goal");
  const completed = {...created, status: "completed", events: [1, 2, 3, 4]};
  const refreshed = mergeRuns([completed], staleRefresh);
  assert.equal(mergeRuns([created], refreshed).find(t => t.id === created.id).status, "completed");
  assert.equal(newestRuns(refreshed)[0].id, created.id);
});
test("stable readable labels retain immutable IDs and legacy directive fallback", () => {
  assert.equal(runTitle(created), "New goal");
  assert.equal(runTitle(old), "Old goal");
  assert.equal(created.id, "T-new");
  assert.equal(runTitle({directive: "Goal ".repeat(30)}).length, 80);
});
test("graph topology uses actual backend stages, not skipped agents", () => {
  assert.deepEqual(graphPath({...created, stages: [{agentId: "data"}, {agentId: "analysis"}, {agentId: "report"}]}),
    ["goal", "data", "analysis", "report", "result"]);
  assert.deepEqual(graphPath({executionMode: "single", stages: [{agentId: "direct"}]}), ["goal", "direct", "result"]);
  assert.deepEqual(graphPath({...old, stages: ["research", "data", "analysis", "summarizer", "report"].map(agentId => ({agentId}))}),
    ["goal", "orchestrator", "research", "data", "analysis", "summarizer", "report", "result"]);
  assert.ok(workspaceSubtitle("adaptive").includes("Rule-selected"));
  assert.ok(!workspaceSubtitle("single").includes("Five"));
});
test("dataset options use only registered active metadata and explicit empty state", () => {
  assert.deepEqual(datasetOptions([]), []);
  assert.match(DATASET_EMPTY, /No benchmark datasets are registered on this deployment/);
  assert.match(DATASET_EMPTY, /administrator/);
  assert.deepEqual(datasetOptions([{datasetId: "hr_small", active: true, family: "hr", sizeVariant: "small", recordCount: 62},
    {datasetId: "employee_small", active: false}]), [{id: "hr_small", label: "HR · Small · 62 records"}]);
});
