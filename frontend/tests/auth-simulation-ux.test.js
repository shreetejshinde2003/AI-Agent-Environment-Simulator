import {before, after, test} from "node:test";
import assert from "node:assert/strict";
import {createElement} from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {createServer} from "vite";
import {sessionPresentation} from "../src/utils/sessionPresentation.js";
let server, Login, SessionState, RunProgress, Button, auth, parser, RunConfigurationForm, Topbar;
before(async () => {
  server = await createServer({root: new URL("../", import.meta.url).pathname, envDir: false,
    server: {middlewareMode: true, hmr: false, ws: false, watch: null}, logLevel: "error"});
  ({default: Login} = await server.ssrLoadModule("/src/pages/Login.jsx"));
  ({default: SessionState} = await server.ssrLoadModule("/src/components/common/SessionState.jsx"));
  ({default: RunProgress} = await server.ssrLoadModule("/src/components/dashboard/RunProgress.jsx"));
  ({default: Topbar} = await server.ssrLoadModule("/src/layout/Topbar.jsx"));
  ({default: Button} = await server.ssrLoadModule("/src/components/common/Button.jsx"));
  ({RunConfigurationForm} = await server.ssrLoadModule("/src/components/dashboard/CreateTaskModal.jsx"));
  auth = await server.ssrLoadModule("/src/services/authClient.js");
  ({parseApiResponse: parser} = await server.ssrLoadModule("/src/services/apiResponse.js"));
});
after(async () => {await server?.close();});
const render = (Component, props) => renderToStaticMarkup(createElement(Component, props));
for (const [error, title, signIn] of [
  [{status: 503}, "Server unavailable", false],
  [{status: 401, code: "session_expired"}, "Session expired", true],
  [{status: 401, code: "session_revoked"}, "Sign in again", true],
  [{code: "oauth_sign_in_failed"}, "Sign-in could not finish", true],
  [{status: 401, code: "session_changed"}, "Browser account changed", false],
  [{status: 403, code: "user_unavailable"}, "Access unavailable", true],
  [{name: "TimeoutError"}, "Connection timed out", false],
  [new TypeError("PRIVATE token"), "Connection interrupted", false],
  [{status: 401, code: "unexpected_api_response"}, "Unable to connect", false],
  [{status: 200, code: "unexpected_api_response"}, "Unable to connect", false],
]) test(`safe authentication presentation: ${title}`, () => {
  const props = {error: {...error, message: "PRIVATE token and OAuth diagnostic"}, onRetry() {}};
  const feedback = sessionPresentation(props.error);
  assert.equal(feedback.title, title);
  assert.equal(!!feedback.signIn, signIn);
  const html = render(Login, props);
  assert.ok(html.includes(title));
  assert.match(html, /Continue with Google/);
  assert.doesNotMatch(html, /PRIVATE|OAuth diagnostic/);
  assert.equal(html.includes("Retry connection"), !signIn);
});
test("anonymous login has no spurious error or automatic redirect", () => {
  const html = render(Login, {});
  assert.match(html, /Sign in to continue/); assert.doesNotMatch(html, /role="alert"|Retry connection/);
});
test("bootstrap announces loading, then a recoverable workspace error", () => {
  assert.match(render(SessionState, {title: "Loading your workspaces…", description: "Preparing access"}), /aria-busy="true"/);
  const html = render(SessionState, {context: "workspace", error: {status: 404}, onRetry() {}});
  assert.match(html, /Workspace unavailable/); assert.match(html, /Try again/); assert.match(html, /role="alert"/);
});
test("expired and revoked sessions retain backend codes while anonymous 401 remains null", async () => {
  const original = globalThis.fetch;
  try {
    for (const code of ["session_expired", "session_revoked", "invalid_session", "user_unavailable"]) {
      globalThis.fetch = async () => Response.json({detail: {code, message: "PRIVATE"}}, {status: 401});
      await assert.rejects(auth.getCurrentUser, error => error.code === code && error.status === 401);
    }
    globalThis.fetch = async () => Response.json({detail: {code: "not_authenticated"}}, {status: 401});
    assert.equal(await auth.getCurrentUser(), null);
  } finally {globalThis.fetch = original;}
});
test("only a parsed API 401 emits the session event; permission and proxy failures do not", async () => {
  const original = globalThis.window;
  const events = [];
  globalThis.window = {dispatchEvent: event => events.push(event)};
  try {
    for (const status of [401, 403, 503]) await assert.rejects(parser(Response.json({detail: {code: "session_expired"}}, {status}), "/api/v1/tasks"));
    await assert.rejects(parser(new Response("PRIVATE HTML", {status: 401, headers: {"Content-Type": "text/html"}}), "/api/v1/tasks"));
    await assert.rejects(parser(Response.json({detail: {code: "session_expired"}}, {status: 401}), "/api/v1/auth/me"));
    assert.equal(events.length, 1); assert.equal(events[0].type, "session-unavailable");
    assert.equal(events[0].detail.code, "session_expired");
  } finally {if (original === undefined) delete globalThis.window; else globalThis.window = original;}
});
test("run progress uses recorded active stages and excludes skipped specialists", () => {
  const task = {status: "in_progress", stages: [{agentId: "data", status: "completed"}, {agentId: "analysis", status: "active"}, {agentId: "report", status: "waiting"}, {agentId: "research", status: "skipped"}]};
  const html = render(RunProgress, {task, agents: [{id: "analysis", name: "Analysis Agent"}]});
  assert.match(html, /Working: Analysis Agent/); assert.match(html, /1 of 3 recorded stages completed · 1 skipped/);
  assert.doesNotMatch(html, /%|estimated|Final answer available/);
});
test("failed run exposes real review actions and keeps the recorded failure escaped", () => {
  const html = render(RunProgress, {task: {status: "failed", error: "<script>fixture</script>", stages: [{agentId: "analysis", status: "failed"}]}, onInspect() {}});
  assert.match(html, /Review failed stage: analysis/); assert.match(html, /Recorded failure/);
  assert.match(html, /&lt;script&gt;/); assert.doesNotMatch(html, /<script>|Resume|Retry execution/);
});
test("completed and queued states distinguish answer availability without fabrication", () => {
  assert.match(render(RunProgress, {task: {status: "queued"}}), /Waiting to start/);
  assert.match(render(RunProgress, {task: {status: "completed", output: "fixture"}}), /Final answer available/);
  assert.match(render(RunProgress, {task: {status: "completed", output: null}}), /no final answer was recorded/);
});
test("shared Button retains variant styling when a caller adds a class", () => {
  const html = render(Button, {variant: "primary", className: "fixture-class", disabled: true, children: "Run"});
  assert.match(html, /class="btn btn-primary fixture-class"/); assert.match(html, /type="button"/); assert.match(html, /disabled=""/);
});
test("composer keeps optional context subordinate and disables unavailable specialist utility", () => {
  const html = render(RunConfigurationForm, {draft: {directive: "", title: "", executionMode: "fixed", datasetId: ""}, agents: [], datasets: [], uploads: [], onChange() {}});
  assert.match(html, /Task · required/); assert.match(html, /rows="6"/); assert.match(html, /<details class="composer-context"><summary/);
  assert.match(html, /No executable specialists/); assert.match(html, /disabled="" aria-label="Individual Specialist/);
});

test("readiness distinguishes available refresh from simulation data failure", () => {
  const props = {backendStatus: "connected", workspaceStatus: "ready", socketStatus: "offline"};
  assert.match(render(Topbar, props), /Ready/);
  const html = render(Topbar, {...props, dataStatus: "error"});
  assert.match(html, /Connection problem/); assert.match(html, /Backend reachable/);
  assert.doesNotMatch(html, /Ready/);
});
