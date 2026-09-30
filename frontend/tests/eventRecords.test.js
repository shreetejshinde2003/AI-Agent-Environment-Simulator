import test from "node:test";
import assert from "node:assert/strict";
import {workspaceRecords, recordTarget, recordMatchesTarget, selectedRecord} from "../src/utils/eventRecords.js";
import {resolveInspectorTarget} from "../src/utils/workspaceSelection.js";
import {canvasPath, edgeView, graphFitKey, GRAPH_FIT_OPTIONS, stageView} from "../src/utils/graphPresentation.js";
import {adaptiveRun, singleRun, fixedRun, legacyRun, failedRun} from "./fixtures/inspectorRuns.js";
import {getViewportForBounds} from "reactflow";

test("stage lifecycle and failure events use persisted agent identities", () => {
  for (const type of ["agent_started", "agent_completed", "agent_failed"]) {
    assert.deepEqual(recordTarget(adaptiveRun, {source: "event", record: {id: type, type, agentId: "analysis"}}), {kind: "stage", id: "analysis"});
  }
  const failure = workspaceRecords(failedRun).find(row => row.record.type === "agent_failed");
  assert.deepEqual(recordTarget(failedRun, failure), {kind: "stage", id: "analysis"});
  assert.equal(stageView(failedRun, failedRun.stages[2]).text, "Not executed");
  assert.equal(workspaceRecords(failedRun).some(row => row.source === "handoff" && row.record.fromAgentId === "analysis"), false);
});

test("only an actual message record can open its handoff without guessing", () => {
  const rows = workspaceRecords(adaptiveRun);
  const handoff = rows.find(row => row.source === "handoff");
  assert.deepEqual(recordTarget(adaptiveRun, handoff), {kind: "handoff", id: handoff.record.id});
  const event = {source: "event", record: {id: "message-event", type: "message_created", agentId: "analysis", text: "analysis → report: insights", timestamp: handoff.record.timestamp}};
  assert.deepEqual(recordTarget(adaptiveRun, event), {kind: "event", source: "event", id: "message-event"});
});

test("route and completion events open existing route/result objects only", () => {
  const row = workspaceRecords(adaptiveRun).find(row => row.record.type === "route_planned");
  assert.deepEqual(recordTarget(adaptiveRun, row), {kind: "route"});
  assert.equal(recordTarget({...adaptiveRun, routePlan: null}, row).kind, "event");
  assert.equal(recordTarget(singleRun, row).kind, "event");
  const completion = {source: "event", record: {id: "done", type: "simulation_completed"}};
  assert.deepEqual(recordTarget(singleRun, completion), {kind: "result"});
  assert.equal(recordTarget({...singleRun, status: "in_progress"}, completion).kind, "event");
  const failure = {source: "event", record: {id: "failed", type: "simulation_failed"}};
  assert.deepEqual(recordTarget(failedRun, failure), {kind: "run"});
});

test("unknown events and missing agent relations remain safely inspectable", () => {
  const row = {source: "event", record: {id: "unknown", type: "new_type", agentId: "missing"}};
  assert.deepEqual(recordTarget(adaptiveRun, row), {kind: "event", source: "event", id: "unknown"});
  assert.equal(recordTarget(null, row), null);
  const activity = workspaceRecords(adaptiveRun).find(row => row.source === "activity");
  assert.equal(recordTarget(adaptiveRun, activity).kind, "event");
});

test("record IDs are source-qualified and timestamp ordering never synthesizes time", () => {
  const task = {events: [{id: "same", type: "custom", timestamp: "2026-09-30T10:00:00Z"}],
    messages: [{id: "same", timestamp: "2026-09-30T10:00:01Z"}], activities: [{id: "same"}]};
  const rows = workspaceRecords(task);
  assert.deepEqual(rows.map(row => row.key), ["handoff:same", "event:same", "activity:same"]);
  assert.equal(rows[0].record.timestamp, task.messages[0].timestamp);
  assert.equal(rows[2].record.timestamp, undefined);
  assert.deepEqual(workspaceRecords(null), []);
});

test("event selection resolves from authoritative records and clears on run switch/removal", () => {
  const rows = workspaceRecords(adaptiveRun);
  const row = rows.find(row => row.record.type === "agent_completed" && row.record.agentId === "analysis");
  const selection = {runId: adaptiveRun.id, recordKey: row.key};
  assert.equal(selectedRecord(adaptiveRun, selection, rows), row);
  assert.deepEqual(resolveInspectorTarget(adaptiveRun, selection, rows), {kind: "stage", id: "analysis"});
  assert.equal(resolveInspectorTarget(singleRun, selection), null);
  const refreshed = {...adaptiveRun, events: adaptiveRun.events.filter(event => event.id !== row.record.id)};
  assert.equal(resolveInspectorTarget(refreshed, selection), null);
  assert.equal(selectedRecord(refreshed, selection, workspaceRecords(refreshed)), null);
});

test("object selection correlates only to known records without selecting an invented message event", () => {
  const rows = workspaceRecords(adaptiveRun);
  assert.ok(rows.some(row => recordMatchesTarget(adaptiveRun, row, {kind: "stage", id: "analysis"})));
  const message = rows.find(row => row.source === "handoff");
  assert.equal(recordMatchesTarget(adaptiveRun, message, {kind: "handoff", id: message.record.id}), true);
  assert.equal(recordMatchesTarget(adaptiveRun, message, {kind: "stage", id: "research"}), false);
  assert.equal(recordMatchesTarget(adaptiveRun, rows.find(row => row.record.type === "route_planned"), {kind: "route"}), true);
});

test("live authoritative snapshots update stage states, keep selected identity, then become static", () => {
  const waiting = structuredClone(adaptiveRun);
  waiting.status = "queued"; waiting.messages = []; waiting.events = [];
  waiting.stages.forEach(stage => {stage.status = "waiting"; stage.startedAt = null;});
  const selection = {runId: waiting.id, target: {kind: "stage", id: "data"}};
  assert.equal(stageView(waiting, waiting.stages[0]).text, "Selected · waiting");
  const running = structuredClone(waiting);
  running.status = "in_progress"; running.stages[0].status = "active";
  running.events = [{id: "started", type: "agent_started", agentId: "data", timestamp: "2026-09-30T10:00:01Z"}];
  assert.equal(stageView(running, running.stages[0]).text, "Running");
  assert.deepEqual(resolveInspectorTarget(running, selection), selection.target);
  const next = structuredClone(running); next.stages[0].status = "completed"; next.stages[1].status = "active";
  assert.equal(stageView(next, next.stages[0]).text, "Completed");
  assert.equal(stageView(next, next.stages[1]).text, "Running");
  assert.equal(graphFitKey(next), graphFitKey(running));
  for (const message of adaptiveRun.messages) assert.equal(edgeView(adaptiveRun, message.fromAgentId, message.toAgentId, {}, message).animated, false);
  const stageMap = Object.fromEntries(adaptiveRun.stages.map(stage => [stage.agentId, stage]));
  assert.equal(edgeView(adaptiveRun, "route", "data", stageMap).recorded, true);
  assert.equal(edgeView(adaptiveRun, "route", "analysis", stageMap).recorded, false);
  assert.equal(edgeView(waiting, "route", "data", Object.fromEntries(waiting.stages.map(stage => [stage.agentId, stage]))).recorded, false);
});

test("fitting keys follow actual topology and all standard route lengths fit supported panels", () => {
  const paths = [singleRun, fixedRun, adaptiveRun, legacyRun, failedRun];
  assert.equal(canvasPath(singleRun).length, 3);
  assert.equal(canvasPath(fixedRun).length, 8);
  assert.equal(canvasPath(adaptiveRun).length, 6);
  assert.equal(canvasPath(legacyRun).length, 3);
  assert.notEqual(graphFitKey(singleRun), graphFitKey(fixedRun));
  assert.equal(graphFitKey({...adaptiveRun, status: "in_progress"}), graphFitKey(adaptiveRun));
  for (const task of paths) for (const [width, height] of [[360, 420], [700, 648], [450, 480]]) {
    const bounds = {x: 120, y: 0, width: 230, height: (canvasPath(task).length - 1) * 122 + 110};
    const view = getViewportForBounds(bounds, width, height, GRAPH_FIT_OPTIONS.minZoom, GRAPH_FIT_OPTIONS.maxZoom, GRAPH_FIT_OPTIONS.padding);
    assert.ok(view.x + bounds.x * view.zoom >= 0);
    assert.ok(view.y >= 0);
    assert.ok(view.y + bounds.height * view.zoom <= height);
  }
  assert.equal(GRAPH_FIT_OPTIONS.duration, 0);
});
