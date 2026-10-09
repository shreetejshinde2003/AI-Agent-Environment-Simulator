import {before, after, test} from "node:test";
import assert from "node:assert/strict";
import {createServer} from "vite";
import {setExpectedUser, sessionHeaders, announceSessionChange, watchSessionChanges} from "../src/services/sessionSync.js";
let server, apiClient, workspaceClient, auth;
before(async () => {
  server = await createServer({root: new URL("../", import.meta.url).pathname, envDir: false,
    server: {middlewareMode: true, hmr: false, ws: false, watch: null}, logLevel: "error"});
  ({apiClient} = await server.ssrLoadModule("/src/services/apiClient.js"));
  ({workspaceClient} = await server.ssrLoadModule("/src/services/workspaceClient.js"));
  auth = await server.ssrLoadModule("/src/services/authClient.js");
});
after(async () => {setExpectedUser(null); await server?.close();});
test("REST and logout carry the asserted tab identity; /me discovers the authoritative cookie identity", async () => {
  const sync = await server.ssrLoadModule("/src/services/sessionSync.js");
  const original = globalThis.fetch;
  const seen = [];
  try {
    sync.setExpectedUser({id: "USR-tab"});
    globalThis.fetch = async (url, options) => {
      seen.push({url, options});
      return url.endsWith("/logout") ? new Response(null, {status: 204}) : Response.json([]);
    };
    await apiClient.getTasks("WS-a");
    await workspaceClient.list();
    await auth.logout();
    await auth.getCurrentUser();
    assert.deepEqual(seen.map(r => r.options.headers["X-Expected-User-Id"]), ["USR-tab", "USR-tab", "USR-tab", undefined]);
    assert.equal(seen[0].options.headers["X-Workspace-Id"], "WS-a");
    sync.setExpectedUser(null);
    await apiClient.getTasks("WS-a");
    assert.equal(seen.at(-1).options.headers["X-Expected-User-Id"], undefined);
  } finally {globalThis.fetch = original; sync.setExpectedUser(null);}
});
test("notifications are optional; focus/visibility/periodic fallback survives restricted browser storage and cleans up", () => {
  const original = {window: globalThis.window, document: globalThis.document, BroadcastChannel: globalThis.BroadcastChannel};
  const win = new EventTarget(), doc = new EventTarget();
  let interval, cleared = false, checks = 0;
  win.setInterval = fn => {interval = fn; return 7;};
  win.clearInterval = id => {assert.equal(id, 7); cleared = true;};
  doc.visibilityState = "visible";
  globalThis.window = win; globalThis.document = doc;
  globalThis.BroadcastChannel = class {constructor() {throw new Error("blocked");}};
  try {
    announceSessionChange();
    const stop = watchSessionChanges(() => ++checks);
    win.dispatchEvent(new Event("focus"));
    doc.dispatchEvent(new Event("visibilitychange")); interval();
    assert.equal(checks, 3);
    doc.visibilityState = "hidden"; interval(); assert.equal(checks, 3);
    stop(); win.dispatchEvent(new Event("focus")); doc.dispatchEvent(new Event("visibilitychange"));
    assert.equal(checks, 3); assert.ok(cleared);
  } finally {Object.assign(globalThis, original);}
});
test("broadcast carries only a recheck hint, never user identity or authorization", () => {
  const original = globalThis.BroadcastChannel;
  let posted, closed = false;
  globalThis.BroadcastChannel = class {
    constructor(name) {assert.equal(name, "fmproject-session");}
    postMessage(value) {posted = value;}
    close() {closed = true;}
  };
  try {
    setExpectedUser({id: "USR-private"}); announceSessionChange();
    assert.equal(posted, "recheck"); assert.ok(closed);
    assert.equal(sessionHeaders()["X-Expected-User-Id"], "USR-private");
    setExpectedUser(null); assert.deepEqual(sessionHeaders(), {});
  } finally {globalThis.BroadcastChannel = original; setExpectedUser(null);}
});
