import {after, before, test} from "node:test";
import assert from "node:assert/strict";
import {fileURLToPath} from "node:url";
import {createElement} from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {createServer} from "vite";

let server, Organizations, organizationNameError, joinCodeError, workspaceClient;

before(async () => {
  server = await createServer({
    root: fileURLToPath(new URL("../", import.meta.url)),
    envDir: false,
    define: {
      "import.meta.env.VITE_API_BASE_URL": JSON.stringify("http://fixture.invalid"),
      "import.meta.env.DEV": "true",
    },
    server: {middlewareMode: true, hmr: false, ws: false, watch: null},
    logLevel: "error",
  });
  ({default: Organizations} = await server.ssrLoadModule("/src/pages/Organizations.jsx"));
  ({organizationNameError, joinCodeError} =
    await server.ssrLoadModule("/src/utils/organizationValidation.js"));
  ({workspaceClient} = await server.ssrLoadModule("/src/services/workspaceClient.js"));
});

after(async () => { await server?.close(); });

test("organization page exposes only private create/join membership actions", () => {
  const html = renderToStaticMarkup(createElement(Organizations));
  assert.match(html, /Workspace access/);
  assert.match(html, /Create Organization/);
  assert.match(html, /Join Organization/);
  assert.match(html, /private code provided directly/);
  assert.match(html, /does not change simulation ownership yet/);
  assert.doesNotMatch(html, /Browse organizations|Search organizations|Discover organizations/i);
  assert.doesNotMatch(html, /workspace switcher|switch workspace/i);
});

test("organization forms use bounded native inputs and do not echo invalid values", () => {
  const html = renderToStaticMarkup(createElement(Organizations));
  assert.match(html, /id="organization-name"/);
  assert.match(html, /maxLength="120"/);
  assert.match(html, /autoComplete="organization"/);
  assert.match(html, /id="organization-join-code"/);
  assert.match(html, /maxLength="64"/);
  assert.match(html, /autoComplete="off"/);
  assert.match(organizationNameError("   "), /Enter an organization name/);
  assert.match(organizationNameError("x".repeat(121)), /120/);
  assert.equal(organizationNameError("  Acme Research  "), null);
  assert.match(joinCodeError("  "), /Enter an organization join code/);
  assert.match(joinCodeError("x".repeat(65)), /supported format/);
  assert.equal(joinCodeError("ABCD-EFGH-IJKL"), null);
});

test("workspace client includes credentials and uses only scoped workspace endpoints", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    calls.push({url: String(url), options});
    return {
      ok: true,
      status: 200,
      async json() { return {personalWorkspace: {id: "W-1"}, organizations: []}; },
    };
  };

  try {
    await workspaceClient.list();
    await workspaceClient.createOrganization("Acme");
    await workspaceClient.joinOrganization("ABCD-EFGH-IJKL");
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(calls.length, 3);
  assert.match(calls[0].url, /\/api\/v1\/workspaces$/);
  assert.match(calls[1].url, /\/api\/v1\/workspaces\/organizations$/);
  assert.match(calls[2].url, /\/api\/v1\/workspaces\/organizations\/join$/);
  assert.ok(calls.every(call => call.options.credentials === "include"));
  assert.equal(calls[1].options.method, "POST");
  assert.equal(JSON.parse(calls[1].options.body).name, "Acme");
  assert.equal(JSON.parse(calls[2].options.body).joinCode, "ABCD-EFGH-IJKL");
});
