import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { edgeView, stageView } from "../src/utils/graphPresentation.js";
import { modeLabel, graphPath, workspaceSubtitle, datasetOptions, DATASET_EMPTY } from "../src/utils/runs.js";

test("stage labels distinguish selected, running, completed, failed, and never started", () => {
  assert.deepEqual(stageView({status: "queued"}, {status: "waiting"}),
    {status: "waiting", text: "Selected · waiting"});
  assert.deepEqual(stageView({status: "failed"}, {status: "waiting"}),
    {status: "not-executed", text: "Not executed"});
  assert.deepEqual(stageView({status: "completed"}, {status: "waiting"}),
    {status: "not-executed", text: "Not executed"});
  assert.deepEqual(stageView({status: "in_progress"}, {status: "active"}),
    {status: "active", text: "Running"});
  assert.deepEqual(stageView({status: "completed"}, {status: "completed"}),
    {status: "completed", text: "Completed"});
  assert.deepEqual(stageView({status: "failed"}, {status: "failed"}),
    {status: "failed", text: "Failed"});
});

test("saved handoffs never imply an ongoing transfer, including while receiver runs", () => {
  const message = {outputKey: "insights"};
  const stages = {report: {status: "active", startedAt: "2026-09-29T15:00:01Z"}};
  assert.deepEqual(edgeView({status: "in_progress"}, "analysis", "report", stages, message),
    {recorded: true, animated: false, label: "insights"});
  assert.deepEqual(edgeView({status: "completed"}, "analysis", "report", stages, message),
    {recorded: true, animated: false, label: "insights"});
  assert.deepEqual(edgeView({status: "failed"}, "analysis", "report", {}, null),
    {recorded: false, animated: false, label: ""});
  assert.deepEqual(graphPath({executionMode: "adaptive", stages: [{agentId: "analysis"}, {agentId: "report"}]}),
    ["goal", "analysis", "report", "result"]);
});

test("mode descriptions remain accurate and benchmark options require registry entries", () => {
  assert.match(workspaceSubtitle("single"), /direct baseline/);
  assert.match(workspaceSubtitle("fixed"), /Five collaborating specialists/);
  assert.match(workspaceSubtitle("adaptive"), /Rule-selected specialists/);
  assert.match(workspaceSubtitle("single_agent"), /selected specialist/);
  assert.equal(modeLabel("single"), "Single");
  assert.equal(modeLabel("fixed"), "Fixed");
  assert.equal(modeLabel("adaptive"), "Adaptive · rule-based");
  assert.equal(modeLabel("single_agent"), "Individual specialist");
  assert.deepEqual(datasetOptions([]), []);
  assert.match(DATASET_EMPTY, /No benchmark datasets are registered/);
});

test("reduced-motion stylesheet disables non-essential badge and edge movement", () => {
  const css = readFileSync(new URL("../src/index.css", import.meta.url), "utf8");
  const rules = css.slice(css.indexOf("@media (prefers-reduced-motion: reduce)"));
  assert.match(rules, /animation-duration: 0\.01ms !important/);
  assert.match(rules, /\.badge-pulse \.badge-dot \{ animation: none !important/);
  assert.match(rules, /\.react-flow__edge\.animated path \{ animation: none !important/);
});
