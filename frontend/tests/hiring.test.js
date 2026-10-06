import {test, before, after} from "node:test";
import assert from "node:assert/strict";
import {hiringForm, hiringPayload, hiringStatuses} from "../src/utils/hiring.js";
import {createServer} from "vite";
import {fileURLToPath} from "node:url";
test("requirement forms validate and normalize structured fields", () => {
  const form = {...hiringForm("requirements"), title: " Engineer ", purpose: " Build ", responsibilities: "Build\n\n Review ", openings: "2"};
  const result = hiringPayload("requirements", form);
  assert.equal(result.title, "Engineer"); assert.deepEqual(result.responsibilities, ["Build", "Review"]); assert.equal(result.openings, 2);
  assert.equal(result.workspaceId, undefined);
  for (const openings of ["0", "1.5", "NaN", "10001"]) assert.throws(() => hiringPayload("requirements", {...form, openings}));
  assert.throws(() => hiringPayload("requirements", {...form, purpose: " "}));
});
test("knowledge editing retains structured content and optimistic revision", () => {
  const form = hiringForm("role-knowledge", {title: "Engineer", competencies: ["Reliability"], evaluationCriteria: ["Explain tradeoffs"]});
  const result = hiringPayload("role-knowledge", form, 3);
  assert.equal(result.expectedRevision, 3); assert.deepEqual(result.competencies, ["Reliability"]);
  assert.deepEqual(result.evaluationCriteria, ["Explain tradeoffs"]);
});
test("draft editing pins sources and never fabricates AI provenance", () => {
  const original = {title: "Engineer", summary: "Build services", requirement: {id: "REQ-one", revision: 2}, roleKnowledge: {id: "RK-one", revision: 4}};
  const form = hiringForm("job-descriptions", original);
  const result = hiringPayload("job-descriptions", form, 1);
  assert.deepEqual(result.requirement, original.requirement); assert.deepEqual(result.roleKnowledge, original.roleKnowledge);
  assert.equal(result.status, "draft"); assert.equal(result.generatedBy, undefined);
  assert.equal(hiringPayload("job-descriptions", {...form, roleKnowledge: ""}).roleKnowledge, null);
  for (const requirement of ["", "REQ-one@0"]) assert.throws(() => hiringPayload("job-descriptions", {...form, requirement}));
});
test("lifecycle options respect phase boundaries", () => {
  assert.deepEqual(hiringStatuses("requirements", "draft"), ["draft", "active", "archived"]);
  assert.deepEqual(hiringStatuses("requirements", "active"), ["active", "closed", "archived"]);
  assert.deepEqual(hiringStatuses("requirements", "closed"), ["closed", "archived"]);
  assert.deepEqual(hiringStatuses("job-descriptions", "draft"), ["draft", "archived"]);
  assert.deepEqual(hiringStatuses("role-knowledge", "archived"), ["archived"]);
});
let server, client;
before(async () => {
  server = await createServer({root: fileURLToPath(new URL("../", import.meta.url)), envDir: false,
    define: {"import.meta.env.VITE_API_BASE_URL": JSON.stringify("http://fixture.invalid")},
    server: {middlewareMode: true, hmr: false, ws: false, watch: null}, logLevel: "error"});
  ({apiClient: client} = await server.ssrLoadModule("/src/services/apiClient.js"));
});
after(async () => {await server?.close();});
test("HR API integrates authenticated current workspace requests and revision payloads", async () => {
  const old = globalThis.fetch, requests = [];
  globalThis.fetch = async (url, options) => {requests.push({url, options}); return {ok: true, json: async () => []};};
  try {
    await client.getHiringCapabilities("WS-a");
    await client.getHiringRecords("requirements", "WS-a");
    await client.saveHiringRecord("role-knowledge", null, {title: "Engineer"}, "WS-a");
    await client.saveHiringRecord("job-descriptions", "JD-one", {title: "Engineer", expectedRevision: 2}, "WS-b");
    await client.getHiringRevisions("requirements", "REQ-one", "WS-b");
    assert.deepEqual(requests.map(r => r.url.replace("http://fixture.invalid/api/v1", "")), ["/hiring/capabilities", "/hiring/requirements", "/hiring/role-knowledge", "/hiring/job-descriptions/JD-one", "/hiring/requirements/REQ-one/revisions"]);
    for (const {options} of requests) assert.equal(options.credentials, "include");
    assert.deepEqual(requests.map(r => r.options.headers["X-Workspace-Id"]), ["WS-a", "WS-a", "WS-a", "WS-b", "WS-b"]);
    assert.equal(requests[2].options.method, "POST"); assert.equal(requests[3].options.method, "PUT");
    assert.equal(JSON.parse(requests[3].options.body).expectedRevision, 2);
  } finally {globalThis.fetch = old;}
});
test("HR authorization and revision conflicts surface actionable errors", async () => {
  const old = globalThis.fetch;
  try {
    for (const [status, code] of [[403, "hr_permission_denied"], [409, "revision_conflict"], [404, "hr_record_unavailable"]]) {
      globalThis.fetch = async () => ({ok: false, status, json: async () => ({detail: {code, message: "Reload records"}})});
      await assert.rejects(client.getHiringRecords("requirements", "WS-a"), error => error.status === status && error.code === code);
    }
  } finally {globalThis.fetch = old;}
});
