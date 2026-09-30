import {before, after, test} from "node:test";
import assert from "node:assert/strict";
import {fileURLToPath} from "node:url";
import {createElement} from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {createServer} from "vite";
import {adaptiveRun, singleRun, fixedRun, legacyRun, failedRun, longRun, fixtureAgents, unsafeLookingText} from "./fixtures/inspectorRuns.js";
import {workspaceRecords} from "../src/utils/eventRecords.js";

let server;
let WorkspaceInspector;
let RecordedText;
let ContextualEvents;

before(async () => {
  // Transform the real JSX with the already-installed Vite tooling. No browser,
  // backend, provider, filesystem watcher, or public server is required.
  server = await createServer({
    root: fileURLToPath(new URL("../", import.meta.url)), envDir: false,
    server: {middlewareMode: true, hmr: false, ws: false, watch: null}, logLevel: "error",
  });
  ({default: WorkspaceInspector} = await server.ssrLoadModule("/src/components/dashboard/WorkspaceInspector.jsx"));
  ({default: RecordedText} = await server.ssrLoadModule("/src/components/dashboard/RecordedText.jsx"));
  ({default: ContextualEvents} = await server.ssrLoadModule("/src/components/dashboard/ContextualEvents.jsx"));
});
after(async () => {await server?.close();});

function inspect(task, target = null) {
  return renderToStaticMarkup(createElement(WorkspaceInspector, {task, target, agents: fixtureAgents,
    onShowRun() {}, onInspect() {}}));
}

function metadata(html, label, value) {
  assert.match(html, new RegExp(`<dt>${label}</dt><dd>${value}</dd>`));
}

test("no selection renders the recorded run overview with real mode and ID", () => {
  const html = inspect(adaptiveRun);
  assert.match(html, /Run overview/);
  assert.match(html, /Fixture · Adaptive aggregate report/);
  assert.match(html, /fixture-adaptive/);
  assert.match(html, /data → analysis → report/);
  assert.match(html, /research, summarizer/);
  assert.match(html, /Export TXT/);
  assert.match(html, /Export JSON/);
  assert.match(html, /Export CSV/);
});

test("stage selection renders stored telemetry and source provenance", () => {
  const html = inspect(adaptiveRun, {kind: "stage", id: "analysis"});
  assert.match(html, /Analysis Agent · Completed/);
  assert.match(html, /fixture-model/);
  metadata(html, "Measured duration", "2.00s");
  metadata(html, "Input tokens", "30");
  metadata(html, "Output tokens", "10");
  metadata(html, "Total tokens", "40");
  assert.match(html, /Available run context/);
  assert.match(html, /not proof of what this stage consumed/);
  assert.match(html, /Data Agent → Analysis Agent/);
  assert.match(html, /To Report Agent/);
  assert.match(html, /Fixture analysis output/);
  assert.match(html, /Fixture event: analysis completed/);
  assert.doesNotMatch(html, /<h[1-6][^>]*>Exact model input</);
});

test("final result is a dedicated view with run summary and exports", () => {
  const overview = inspect(singleRun);
  const html = inspect(singleRun, {kind: "result"});
  assert.notEqual(html, overview);
  assert.match(html, /Final result/);
  assert.match(html, /Single Agent · Direct Baseline/);
  metadata(html, "Measured duration", "2.00s");
  metadata(html, "Recorded tokens", "40");
  metadata(html, "Stage attempts", "1");
  metadata(html, "Handoffs", "0");
  assert.match(html, /Fixture direct output/);
  assert.match(html, /Export JSON/);
  assert.doesNotMatch(html, /Uploaded context/);
});

test("adaptive route selection shows a model-free deterministic plan", () => {
  const html = inspect(adaptiveRun, {kind: "route"});
  assert.match(html, /Route decision/);
  assert.match(html, /Deterministic rules/);
  assert.match(html, /rules-v1/);
  assert.match(html, /Data Agent → Analysis Agent → Report Agent/);
  assert.match(html, /Research Agent, Summarizer Agent/);
  assert.match(html, /Fixture decision: structured context supplied/);
  assert.match(html, /valid/);
  assert.doesNotMatch(html, /<dt>(Model|Measured duration|Input tokens|Output tokens|Total tokens)<\/dt>/);
  assert.doesNotMatch(html, /fixture-model/);
});

test("real handoff selection renders persisted content and record identity", () => {
  const html = inspect(adaptiveRun, {kind: "handoff", id: adaptiveRun.messages[0].id});
  assert.match(html, /Data Agent → Analysis Agent/);
  assert.match(html, /structured_data/);
  assert.match(html, /fixture-adaptive-message-0/);
  assert.match(html, /Fixture data output/);
  assert.match(html, /persisted message/);
  assert.doesNotMatch(html, /Fixture analysis output/);
});

test("handoff size distinguishes absent content from a recorded empty string", () => {
  const task = structuredClone(adaptiveRun);
  const target = {kind: "handoff", id: task.messages[0].id};
  task.messages[0].content = null;
  metadata(inspect(task, target), "Characters", "Not recorded");
  assert.match(inspect(task, target), /No handoff content recorded/);
  task.messages[0].content = "";
  metadata(inspect(task, target), "Characters", "0");
  assert.match(inspect(task, target), /Recorded handoff content is empty \(0 characters\)/);
});

test("Single, Fixed and legacy utility overviews retain distinct mode semantics", () => {
  const single = inspect(singleRun);
  const fixed = inspect(fixedRun);
  const legacy = inspect(legacyRun);
  assert.match(single, /Single Agent · Direct Baseline/);
  assert.match(fixed, /Fixed five-agent pipeline/);
  assert.match(legacy, /Individual specialist · research/);
  for (const html of [single, fixed, legacy]) {
    assert.doesNotMatch(html, /aria-label="Routing trace"/);
    assert.doesNotMatch(html, /rules-v1/);
  }
  metadata(single, "Stage attempts", "1");
  metadata(single, "Handoffs", "0");
  metadata(fixed, "Stage attempts", "5");
  metadata(fixed, "Handoffs", "4");
});

test("failure inspection preserves missing-input evidence and downstream nonexecution", () => {
  const html = inspect(failedRun, {kind: "stage", id: "analysis"});
  assert.match(html, /Analysis Agent · Failed/);
  assert.match(html, /missing_required_input/);
  assert.match(html, /structured_data/);
  assert.match(html, /Fixture missing required context/);
  assert.match(html, /not executed: Report Agent/);
  assert.doesNotMatch(html, /Report Agent · Failed/);
  assert.match(html, /No stage output recorded/);
});

test("missing telemetry stays unknown while actual zero remains measurable", () => {
  const task = structuredClone(singleRun);
  task.stages[0].durationSeconds = task.stages[0].totalTokens = task.stages[0].inputTokens = task.stages[0].outputTokens = null;
  const unknown = inspect(task, {kind: "stage", id: "direct"});
  metadata(unknown, "Measured duration", "Not recorded");
  metadata(unknown, "Total tokens", "Not recorded");
  task.stages[0].durationSeconds = task.stages[0].totalTokens = task.stages[0].inputTokens = task.stages[0].outputTokens = 0;
  const zero = inspect(task, {kind: "stage", id: "direct"});
  metadata(zero, "Measured duration", "0.00s");
  metadata(zero, "Total tokens", "0");
});

test("long recorded output escapes HTML and preserves an expandable keyboard-scrollable full record", () => {
  const html = renderToStaticMarkup(createElement(RecordedText, {text: longRun.output, label: "fixture output", limit: 120}));
  assert.doesNotMatch(html, /<script>|<img/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(html, /<details><summary>Show full fixture output/);
  assert.match(html, /tabindex="0" aria-label="Full fixture output"/);
  assert.match(html, /Fixture paragraph with a preserved line break\.\n\n/);
  assert.equal(longRun.output.startsWith(unsafeLookingText), true);
});

test("empty inspector and missing text do not invent output or telemetry", () => {
  const html = inspect(null);
  assert.match(html, /Choose a run to inspect/);
  assert.doesNotMatch(html, /fixture-model|Recorded tokens|Final result/);
  const noText = renderToStaticMarkup(createElement(RecordedText, {text: null, label: "stage output"}));
  assert.match(noText, /No stage output recorded/);
});

test("unlinked message event exposes its own record without fabricating a handoff", () => {
  const task = structuredClone(adaptiveRun);
  task.events.push({id: "unlinked-message", type: "message_created", agentId: "analysis",
    timestamp: "2026-09-30T10:00:06Z", text: "analysis → report: insights"});
  const html = inspect(task, {kind: "event", source: "event", id: "unlinked-message"});
  assert.match(html, /Recorded event details/);
  assert.match(html, /unlinked-message/);
  assert.match(html, /does not store a message ID/);
  assert.match(html, /Inspect related agent: Analysis Agent/);
  assert.doesNotMatch(html, /Recorded handoff|Message ID/);
});

test("contextual entries are keyboard buttons with explicit selected and related semantics", () => {
  const records = workspaceRecords(adaptiveRun);
  const stageRow = records.find(row => row.record.type === "agent_completed" && row.record.agentId === "analysis");
  const html = renderToStaticMarkup(createElement(ContextualEvents, {task: adaptiveRun, records,
    target: {kind: "stage", id: "analysis"}, selectedKey: stageRow.key, onSelect() {}, onShowAll() {}}));
  assert.match(html, /aria-label="Inspect Stage completed/);
  assert.match(html, /aria-pressed="true"/);
  assert.match(html, /Selected record/);
  assert.match(html, /Related to inspected object/);
  assert.match(html, /All records|Run events|Handoffs|Activity/);
  assert.match(html, /View full execution log/);
});

test("selected event context retains its timestamp and ID alongside the stage inspector", () => {
  const selected = workspaceRecords(adaptiveRun).find(row => row.record.type === "agent_completed" && row.record.agentId === "analysis");
  const html = renderToStaticMarkup(createElement(WorkspaceInspector, {task: adaptiveRun,
    agents: fixtureAgents, target: {kind: "stage", id: "analysis"}, selectedRecord: selected,
    onShowRun() {}, onInspect() {}, onInspectRecord() {}}));
  assert.match(html, /Selected record context/);
  assert.match(html, /fixture-adaptive-complete-1/);
  assert.match(html, /dateTime="2026-09-30T10:00:06Z"/);
  assert.match(html, /Inspect latest event/);
});

test("empty contextual stream remains honest and bounded even with large histories", () => {
  const empty = renderToStaticMarkup(createElement(ContextualEvents, {task: null, records: [], onSelect() {}, onShowAll() {}}));
  assert.match(empty, /Choose a run to inspect recorded events/);
  const records = Array.from({length: 100}, (_, i) => ({source: "event", key: `event:${i}`, label: "Run started", record: {
    id: String(i), type: "simulation_started", timestamp: "2026-09-30T10:00:00Z", text: "Recorded fixture event"}}));
  const html = renderToStaticMarkup(createElement(ContextualEvents, {task: adaptiveRun, records, onSelect() {}, onShowAll() {}}));
  assert.equal((html.match(/aria-label="Inspect Run started/g) ?? []).length, 12);
  assert.match(html, /Showing 12 of 100/);
});
