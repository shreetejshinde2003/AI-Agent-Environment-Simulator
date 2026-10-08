import {test, before, after} from "node:test";
import assert from "node:assert/strict";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {createServer} from "vite";
import {fileURLToPath} from "node:url";
import {hrAgentPayload, hrRunPending, hrStructuredOutput} from "../src/utils/hrAgents.js";

test("AI assistance pins requirement and optional knowledge without write authority", () => {
  assert.deepEqual(hrAgentPayload("hr_jd_draft", {id:"HR-a",revision:2}, {id:"RK-a",revision:3}), {
    agentId:"hr_jd_draft",requirement:{id:"HR-a",revision:2},roleKnowledge:{id:"RK-a",revision:3}});
  assert.equal(hrAgentPayload("hr_requirement_analysis",{id:"HR-a",revision:1}).roleKnowledge,null);
  assert.throws(() => hrAgentPayload("hr_jd_draft",null));
});
test("saved draft validation uses its historical sources even if current heads differ", () => {
  const draft={id:"JD-a",revision:4,content:{requirement:{id:"HR-a",revision:1},roleKnowledge:{id:"RK-a",revision:2}}};
  const payload=hrAgentPayload("hr_draft_validation",{id:"HR-a",revision:9},null,draft);
  assert.deepEqual(payload.requirement,draft.content.requirement);
  assert.deepEqual(payload.roleKnowledge,draft.content.roleKnowledge);
  assert.deepEqual(payload.jobDescription,{id:"JD-a",revision:4});
  assert.throws(() => hrAgentPayload("hr_draft_validation",null,null,null));
});
test("only pending authoritative statuses trigger polling", () => {
  for (const status of ["queued","in_progress"]) assert.equal(hrRunPending({status}),true);
  for (const status of ["completed","failed",null]) assert.equal(hrRunPending({status}),false);
});
test("failed output never becomes a successful proposal", () => {
  assert.equal(hrStructuredOutput({status:"failed",output:'{"summary":"fake"}'}),null);
  assert.equal(hrStructuredOutput({status:"queued"}),null);
  assert.deepEqual(hrStructuredOutput({status:"completed",output:'{"summary":"Actual output"}'}),{summary:"Actual output"});
});
let server,client;
before(async () => {
  server=await createServer({root:fileURLToPath(new URL("../",import.meta.url)),envDir:false,
    define:{"import.meta.env.VITE_API_BASE_URL":JSON.stringify("http://fixture.invalid")},
    server:{middlewareMode:true,hmr:false,ws:false,watch:null},logLevel:"error"});
  ({apiClient:client}=await server.ssrLoadModule("/src/services/apiClient.js"));
});
after(async () => {await server?.close();});
test("agent discovery admission polling and history use authenticated workspace APIs", async () => {
  const old=globalThis.fetch, calls=[];
  globalThis.fetch=async (url,options) => {calls.push({url,options});return {headers: new Headers({"Content-Type": "application/json"}), ok: true,json:async () => ({status:"queued"})};};
  try {
    await client.getHRAgents("WS-a"); await client.runHRAgent({agentId:"hr_jd_draft",requirement:{id:"HR-a",revision:1}},"WS-a");
    await client.getHRRun("HRRUN-one","WS-b"); await client.getHRRuns("WS-b");
    assert.deepEqual(calls.map(c=>c.url.replace("http://fixture.invalid/api/v1","")),["/hiring/agents","/hiring/agents/runs","/hiring/agents/runs/HRRUN-one","/hiring/agents/runs"]);
    assert.deepEqual(calls.map(c=>c.options.headers["X-Workspace-Id"]),["WS-a","WS-a","WS-b","WS-b"]);
    assert.ok(calls.every(c=>c.options.credentials==="include"));
    assert.equal(calls[1].options.method,"POST");
    assert.equal(JSON.parse(calls[1].options.body).requirement.revision,1);
  } finally {globalThis.fetch=old;}
});
test("revocation and provider errors are exposed without fabricated results", async () => {
  const old=globalThis.fetch;
  globalThis.fetch=async () => ({headers: new Headers({"Content-Type": "application/json"}), ok: false,status:403,json:async () => ({detail:{code:"hr_permission_denied",message:"Active HR role required"}})});
  try {await assert.rejects(client.getHRRun("HRRUN-one","WS-a"),e=>e.status===403 && e.code==="hr_permission_denied");}
  finally {globalThis.fetch=old;}
});
test("assistance screen renders proposal boundary and real action/history controls", async () => {
  const {default:Component}=await server.ssrLoadModule("/src/components/hiring/HRAssistance.jsx");
  const html=renderToStaticMarkup(React.createElement(Component,{workspaceId:"WS-a",records:{}}));
  assert.match(html,/AI assistance/);assert.match(html,/HR agent action/);assert.match(html,/Persisted HR runs/);
  assert.match(html,/AI outputs are proposals/);assert.match(html,/Run AI assistance/);
  assert.doesNotMatch(html,/Approve job|Publish job/);
});
