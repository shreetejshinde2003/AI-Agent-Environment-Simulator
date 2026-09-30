import {before, after, test} from "node:test";
import assert from "node:assert/strict";
import {fileURLToPath} from "node:url";
import {createElement} from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {createServer} from "vite";
import {filterRuns, runNavigationIndex, runCreatedLabel, RUN_PAGE_SIZE} from "../src/utils/runBrowser.js";
import {validateRunDraft, runRequest, validateReferenceFiles, createRequestLock, specialistAgents} from "../src/utils/runComposer.js";
import {apiError, creationError} from "../src/utils/apiErrors.js";
import {mergeRuns} from "../src/utils/runs.js";
import {singleRun, fixtureAgents} from "./fixtures/inspectorRuns.js";
import {registeredDatasets, acknowledgedFixture, completedFixture} from "./fixtures/composerFixtures.js";

let server, RunPicker, RunConfigurationForm;
before(async () => {
  server = await createServer({root: fileURLToPath(new URL("../", import.meta.url)), envDir: false,
    define: {"import.meta.env.VITE_API_BASE_URL": JSON.stringify("http://fixture.invalid")},
    server: {middlewareMode: true, hmr: false, ws: false, watch: null}, logLevel: "error"});
  ({default: RunPicker} = await server.ssrLoadModule("/src/components/dashboard/RunPicker.jsx"));
  ({RunConfigurationForm} = await server.ssrLoadModule("/src/components/dashboard/CreateTaskModal.jsx"));
});
after(async () => {await server?.close();});
const draft = {directive: "Explain a fixture task", title: "", executionMode: "fixed", assignedAgentId: "research", datasetId: "", taskType: ""};
const noop = () => {};
function form(props = {}) {
  return renderToStaticMarkup(createElement(RunConfigurationForm, {draft, agents: fixtureAgents, datasets: [], uploads: [],
    onChange: noop, onSubmit: noop, onUpload: noop, onDetach: noop, onClose: noop, ...props}));
}

test("run browsing normalizes terms, orders newest first and filters a large history without mutation", () => {
  const tasks = Array.from({length: 1000}, (_, i) => ({id: `fixture-${i}`, title: `Analysis report ${i}`,
    executionMode: i % 2 ? "single" : "full_pipeline", status: i % 3 ? "completed" : "failed", createdAt: "2026-09-01"}));
  tasks.push({...singleRun, id: "fixture-latest", title: "Analysis report latest", createdAt: "2026-09-30"});
  const snapshot = structuredClone(tasks);
  assert.equal(filterRuns(tasks, {query: "  ANALYSIS   report "})[0].id, "fixture-latest");
  assert.equal(filterRuns(tasks, {mode: "fixed"}).length, 500);
  assert.ok(filterRuns(tasks, {status: "failed"}).every(run => run.status === "failed"));
  assert.deepEqual(filterRuns(tasks, {query: "does not exist"}), []);
  assert.deepEqual(tasks, snapshot);
  assert.equal(runCreatedLabel({}), "Time not recorded");
  assert.equal(runCreatedLabel({createdAt: "invalid"}), "Time not recorded");
});

test("run rows keep full accessible titles primary, IDs secondary, selection visible and rendering bounded", () => {
  const title = "Accessible long fixture title ".repeat(10);
  const tasks = Array.from({length: 60}, (_, i) => ({...singleRun, id: `fixture-${i}`, title}));
  const html = renderToStaticMarkup(createElement(RunPicker, {tasks, selectedTask: tasks[0], onSelect: noop}));
  assert.match(html, /Current run: Accessible long fixture title/);
  assert.ok(html.includes(title));
  assert.ok(html.indexOf(`<strong class="run-picker-title">${title}</strong>`) < html.indexOf("ID: fixture-0"));
  assert.match(html, /aria-current="true"/);
  assert.match(html, /Selected/);
  assert.equal((html.match(/data-run-choice=/g) ?? []).length, RUN_PAGE_SIZE);
  assert.match(html, /Showing 20 of 60 matching runs/);
  assert.match(html, /Show more runs/);
  assert.match(html, /Find a run/);
  assert.match(html, /All modes/);
  assert.match(html, /All statuses/);
});

test("run keyboard navigation supports bounded arrows, Home, End and native activation", () => {
  assert.equal(runNavigationIndex("ArrowDown", -1, 20), 0);
  assert.equal(runNavigationIndex("ArrowUp", -1, 20), 19);
  assert.equal(runNavigationIndex("ArrowUp", 0, 20), 0);
  assert.equal(runNavigationIndex("ArrowDown", 19, 20), 19);
  assert.equal(runNavigationIndex("Home", 12, 20), 0);
  assert.equal(runNavigationIndex("End", 0, 20), 19);
  assert.equal(runNavigationIndex("Enter", 0, 20), null);
  assert.equal(runNavigationIndex("ArrowDown", -1, 0), null);
});

test("picker empty, loading and error states do not fabricate runs", () => {
  const picker = extra => renderToStaticMarkup(createElement(RunPicker, {tasks: [], selectedTask: null, onSelect: noop, ...extra}));
  assert.match(picker({}), /No simulation data yet/);
  assert.match(picker({isLoading: true}), /Loading saved simulations/);
  assert.match(picker({loadError: true}), /Unable to load saved simulations/);
  for (const extra of [{}, {isLoading: true}, {loadError: true}]) assert.doesNotMatch(picker(extra), /data-run-choice=/);
});

test("composer explains three research strategies with native labelled radios and a separate specialist utility", () => {
  const html = form();
  assert.match(html, /Goal \/ directive/);
  assert.match(html, /required="" maxLength="10000"/);
  assert.match(html, /Run title · optional/);
  assert.match(html, /maxLength="120"/);
  assert.equal((html.match(/name="executionMode"/g) ?? []).length, 4);
  assert.match(html, /One Direct Agent model call/);
  assert.match(html, /Research → Data → Analysis → Summarizer → Report/);
  assert.match(html, /Rules select specialists using task capabilities and available validated inputs/);
  assert.match(html, /routing uses no model call/);
  assert.match(html, /Individual Specialist · legacy utility/);
  assert.match(html, /Separate from the Single, Fixed and Adaptive research baselines/);
  assert.match(html, /aria-describedby="strategy-adaptive-help"/);
  assert.doesNotMatch(html, /Web Search|Retry|Pause|Evaluation score|better|superior/);
});

test("composer benchmark states are explicit and options contain only active registry metadata", () => {
  assert.match(form(), /No benchmark datasets are registered on this deployment/);
  assert.match(form(), /None · no benchmark context/);
  assert.match(form({datasets: null}), /Loading registered datasets/);
  assert.match(form({datasets: null, datasetError: true}), /Benchmark registry unavailable/);
  const html = form({datasets: registeredDatasets, draft: {...draft, datasetId: "fixture-employee-small"}});
  assert.match(html, /Employee · Small · 3 records/);
  assert.match(html, /HR · Medium · 5 records/);
  assert.doesNotMatch(html, /fixture-inactive|HR · Large/);
  assert.match(html, /server validates its private file/);
  assert.match(html, /bounded, non-personal aggregates/);
  assert.doesNotMatch(html, /EmployeeName|PerformanceRating|ManagerID/);
});

test("composer validates required and bounded inputs without changing backend payload conventions", () => {
  const validate = patch => validateRunDraft({...draft, ...patch}, fixtureAgents, registeredDatasets);
  assert.match(validate({directive: "  "}), /Enter a goal/);
  assert.match(validate({directive: "x".repeat(10001)}), /10,000/);
  assert.match(validate({title: "x".repeat(121)}), /120/);
  assert.match(validate({executionMode: "unknown"}), /available execution/);
  assert.match(validate({datasetId: "fixture-inactive"}), /unavailable/);
  assert.match(validate({executionMode: "adaptive", taskType: "invented"}), /supported/);
  assert.match(validate({executionMode: "single_agent", assignedAgentId: "direct"}), /executable specialist/);
  assert.equal(validate({executionMode: "adaptive", taskType: "analysis"}), null);
  for (const mode of ["single", "fixed", "adaptive", "single_agent"]) {
    const payload = runRequest({...draft, directive: "  Explain fixture  ", title: "  Label  ", executionMode: mode}, [{id: "fixture-upload"}]);
    assert.equal(payload.directive, "Explain fixture"); assert.equal(payload.title, "Label");
    assert.equal(payload.executionMode, mode);
    assert.equal(payload.assignedAgentId, {single: "direct", fixed: "orchestrator", adaptive: "orchestrator", single_agent: "research"}[mode]);
    assert.deepEqual(payload.uploadIds, mode === "single_agent" ? [] : ["fixture-upload"]);
  }
  assert.ok(specialistAgents(fixtureAgents).every(agent => !["direct", "orchestrator", "websearch"].includes(agent.id)));
});

test("legacy utility exposes only executable specialists and does not imply upload consumption", () => {
  const html = form({draft: {...draft, executionMode: "single_agent"}});
  assert.match(html, /<select id="task-agent"/);
  assert.match(html, /Reference uploads are not sent by this legacy utility/);
  assert.doesNotMatch(html, /id="context-files"|<option[^>]*value="direct"|<option[^>]*value="websearch"/);
});

test("reference upload preflight checks the whole batch and a synchronous lock prevents double submission", () => {
  assert.equal(validateReferenceFiles([{name: "fixture.TXT", size: 20}], 0), null);
  assert.match(validateReferenceFiles([{name: "good.csv", size: 20}, {name: "bad.pdf", size: 20}], 0), /TXT, CSV or JSON/);
  assert.match(validateReferenceFiles([{name: "large.json", size: 262145}], 0), /256 KiB/);
  assert.match(validateReferenceFiles([{name: "empty.txt", size: 0}], 0), /empty/);
  assert.match(validateReferenceFiles([{name: "fourth.txt", size: 2}], 3), /three/);
  const lock = createRequestLock();
  assert.equal(lock.acquire(), true); assert.equal(lock.acquire(), false);
  lock.release(); assert.equal(lock.acquire(), true);
});

test("busy composer disables configuration and actions, preserves draft, and distinguishes upload from submit", () => {
  const html = form({work: "submitting"});
  assert.match(html, /aria-busy="true"/);
  assert.match(html, /class="composer-fields" disabled=""/);
  assert.match(html, /Submitting run/);
  assert.match(html, /Keep this dialog open/);
  assert.match(html, /Explain a fixture task/);
  assert.match(html, /type="submit"[^>]*disabled=""/);
  assert.match(form({work: "uploading"}), /Uploading reference data/);
  assert.match(form({draft: {...draft, directive: " "}}), /type="submit"[^>]*disabled=""/);
});

test("structured API errors are readable without echoing validation input and uncertain creation never claims failure or success", () => {
  const invalid = apiError({code: "invalid_route", message: "Required input missing"}, 422);
  assert.equal(invalid.message, "Required input missing"); assert.equal(invalid.code, "invalid_route");
  assert.equal(creationError(invalid).outcomeUnknown, false);
  const validation = apiError([{loc: ["body", "directive"], msg: "Too long", input: "private fixture input"}], 422);
  assert.equal(validation.message, "directive: Too long");
  assert.ok(!validation.message.includes("private"));
  assert.equal(creationError(new Error("Connection interrupted")).outcomeUnknown, true);
  const unknown = creationError(apiError("Service unavailable", 503));
  const html = form({error: unknown});
  assert.match(html, /role="alert"/);
  assert.match(html, /submission outcome is not confirmed/);
  assert.match(html, /Check Simulation History before submitting again/);
  assert.doesNotMatch(html, /created successfully/);
});

test("server acknowledgement survives stale refresh and later authoritative completion updates the same immutable ID", () => {
  const acknowledged = acknowledgedFixture(runRequest({...draft, executionMode: "single"}, []), 1);
  const accepted = mergeRuns([acknowledged], [singleRun]);
  const stale = mergeRuns([singleRun], accepted);
  assert.equal(stale.find(run => run.id === acknowledged.id).status, "queued");
  const completed = completedFixture(acknowledged);
  const updated = mergeRuns([completed], stale);
  assert.equal(updated.find(run => run.id === acknowledged.id).status, "completed");
  assert.equal(mergeRuns([acknowledged], updated).find(run => run.id === acknowledged.id).status, "completed");
  assert.equal(completed.id, acknowledged.id);
});

test("untrusted titles, goals and uploaded previews remain escaped, selectable text", () => {
  const unsafe = "<script>fixture</script><img src=x onerror=fixture()>";
  const html = form({draft: {...draft, title: unsafe, directive: unsafe}, uploads: [{id: "fixture-u", filename: "fixture.txt", sizeBytes: 2, preview: unsafe}]});
  assert.doesNotMatch(html, /<script>|<img/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /<pre tabindex="0" aria-label="Prepared preview/);
  assert.match(html, /does not delete the stored upload/);
  assert.match(html, /Uploads are not automatically anonymized/);
  const picker = renderToStaticMarkup(createElement(RunPicker, {tasks: [{...singleRun, title: unsafe}], selectedTask: {...singleRun, title: unsafe}, onSelect: noop}));
  assert.doesNotMatch(picker, /<script>|<img/);
});
