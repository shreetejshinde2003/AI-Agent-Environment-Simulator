import {test} from "node:test";
import assert from "node:assert/strict";
import {canManageAgents, emptyAgentConfig, validateAgentConfig, validateAgentInput} from "../src/utils/agentBuilder.js";
const valid = {...emptyAgentConfig, name: "Reviewer", purpose: "Review", instructions: "Summarize supplied text"};
test("agent management follows workspace IAM and not HR roles", () => {
  for (const [workspace, allowed] of [[null, false], [{kind: "personal"}, true], [{kind: "organization", membershipRole: "owner"}, true], [{kind: "organization", membershipRole: "admin"}, true], [{kind: "organization", membershipRole: "member", humanRoles: ["hr_approver"]}, false]]) assert.equal(canManageAgents(workspace), allowed);
});
test("configuration requires meaningful bounded fields", () => {
  assert.equal(validateAgentConfig(valid), null);
  for (const field of ["name", "purpose", "instructions"]) assert.ok(validateAgentConfig({...valid, [field]: " "}));
  for (const [field, length] of [["name", 81], ["description", 1001], ["purpose", 1001], ["instructions", 8001]]) assert.ok(validateAgentConfig({...valid, [field]: "x".repeat(length)}));
});
test("only supported models and bounded execution settings pass", () => {
  for (const [field, value] of [["model", "arbitrary"], ["provider", "openai"], ["capability", "shell"], ["inputContract", "file"], ["outputContract", "json"], ["maxTokens", 1025], ["maxTokens", 1.5], ["timeoutSeconds", 121], ["timeoutSeconds", 0]]) assert.ok(validateAgentConfig({...valid, [field]: value}));
  assert.equal(validateAgentConfig({...valid, model: "fast", maxTokens: 64, timeoutSeconds: 1, active: false}), null);
});
test("run input validates before submission", () => {
  assert.ok(validateAgentInput(" ")); assert.ok(validateAgentInput("x".repeat(10001)));
  assert.equal(validateAgentInput("Summarize this"), null);
});

import {before, after} from "node:test";
import {fileURLToPath} from "node:url";
import {createServer} from "vite";
import {createElement} from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {modeLabel, graphPath} from "../src/utils/runs.js";
let server, client, Builder;
before(async () => {
  server = await createServer({root: fileURLToPath(new URL("../", import.meta.url)), envDir: false,
    define: {"import.meta.env.VITE_API_BASE_URL": JSON.stringify("http://fixture.invalid")},
    server: {middlewareMode: true, hmr: false, ws: false, watch: null}, logLevel: "error"});
  ({apiClient: client} = await server.ssrLoadModule("/src/services/apiClient.js"));
  ({default: Builder} = await server.ssrLoadModule("/src/components/dashboard/AgentBuilder.jsx"));
});
after(async () => {await server?.close();});
test("builder API client sends authenticated workspace-scoped definitions revisions and runs", async () => {
  const original = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (url, options) => {requests.push({url, options}); return {headers: new Headers({"Content-Type": "application/json"}), ok: true, json: async () => ({id: "fixture"})};};
  try {
    await client.getCustomAgents("WS-fixture");
    await client.getAgentBuilderOptions("WS-fixture");
    await client.saveCustomAgent(null, valid, "WS-fixture");
    await client.saveCustomAgent("CA-fixture", {...valid, expectedRevision: 1}, "WS-fixture");
    await client.getCustomAgentRevisions("CA-fixture", "WS-fixture");
    await client.runCustomAgent("CA-fixture", {text: "input", expectedRevision: 2}, "WS-fixture");
    assert.deepEqual(requests.map(r => r.url.replace("http://fixture.invalid/api/v1", "")), ["/agent-builder", "/agent-builder/options", "/agent-builder", "/agent-builder/CA-fixture", "/agent-builder/CA-fixture/revisions", "/agent-builder/CA-fixture/runs"]);
    for (const {options} of requests) {assert.equal(options.credentials, "include"); assert.equal(options.headers["X-Workspace-Id"], "WS-fixture");}
    assert.equal(requests[2].options.method, "POST"); assert.equal(requests[3].options.method, "PUT");
    assert.equal(JSON.parse(requests[5].options.body).expectedRevision, 2);
  } finally {globalThis.fetch = original;}
});
test("builder surfaces API conflicts and uncertain run acknowledgement without fabricating output", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => ({headers: new Headers({"Content-Type": "application/json"}), ok: false, status: 409, json: async () => ({detail: {code: "revision_conflict", message: "Reload before running"}})});
    await assert.rejects(client.runCustomAgent("CA-fixture", {text: "input", expectedRevision: 1}, "WS-fixture"), error => error.status === 409 && error.code === "revision_conflict" && !error.outcomeUnknown);
    globalThis.fetch = async () => {throw new Error("Connection lost");};
    await assert.rejects(client.runCustomAgent("CA-fixture", {text: "input", expectedRevision: 1}, "WS-fixture"), error => error.outcomeUnknown === true);
  } finally {globalThis.fetch = original;}
});
test("builder loading and management affordances respect IAM in rendered UI", () => {
  const owner = renderToStaticMarkup(createElement(Builder, {workspaceId: "WS-fixture", workspace: {kind: "personal"}}));
  const member = renderToStaticMarkup(createElement(Builder, {workspaceId: "WS-fixture", workspace: {kind: "organization", membershipRole: "member"}}));
  assert.match(owner, /Loading agents/); assert.match(owner, /New agent/); assert.doesNotMatch(member, /New agent/);
});
test("custom execution keeps a distinct mode and only its saved stage in the graph", () => {
  assert.equal(modeLabel("custom"), "Custom agent");
  assert.deepEqual(graphPath({executionMode: "custom", stages: [{agentId: "CA-fixture"}]}), ["goal", "CA-fixture", "result"]);
});
