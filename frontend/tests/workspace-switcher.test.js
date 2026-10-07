import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

let server, WorkspaceSwitcher, resolveActiveWorkspaceId, workspaceOptions;

before(async () => {
  server = await createServer({
    root: fileURLToPath(new URL("../", import.meta.url)),
    envDir: false,
    server: { middlewareMode: true, hmr: false, ws: false, watch: null },
    logLevel: "error",
  });
  ({ default: WorkspaceSwitcher } = await server.ssrLoadModule("/src/layout/WorkspaceSwitcher.jsx"));
  ({ resolveActiveWorkspaceId, workspaceOptions } =
    await server.ssrLoadModule("/src/utils/workspaces.js"));
});

after(async () => { await server?.close(); });

const fixture = {
  personalWorkspace: {
    id: "WS-personal",
    kind: "personal",
    name: "Personal Workspace",
    membershipRole: null,
  },
  organizations: [
    {
      id: "WS-iict",
      kind: "organization",
      name: "IICT",
      membershipRole: "owner",
    },
  ],
};

test("workspace options keep Personal Workspace first and include only discovered organizations", () => {
  assert.deepEqual(workspaceOptions(fixture).map(item => item.id), ["WS-personal", "WS-iict"]);
  assert.deepEqual(workspaceOptions(null), []);
});

test("workspace selection preserves an accessible preference and safely falls back to Personal Workspace", () => {
  assert.equal(resolveActiveWorkspaceId(fixture, "WS-iict"), "WS-iict");
  assert.equal(resolveActiveWorkspaceId(fixture, "WS-unknown"), "WS-personal");
  assert.equal(resolveActiveWorkspaceId(fixture, null), "WS-personal");
});

test("workspace switcher exposes Personal Workspace and IICT with current membership context", () => {
  const html = renderToStaticMarkup(createElement(WorkspaceSwitcher, {
    workspaces: workspaceOptions(fixture),
    activeWorkspace: fixture.organizations[0],
    status: "ready",
  }));

  assert.match(html, /Workspace/);
  assert.match(html, /Personal Workspace/);
  assert.match(html, /IICT/);
  assert.match(html, /Owner · Organization/);
  assert.match(html, /aria-label="Active workspace"/);
});

test("workspace membership label preserves Admin without implying HR authority", () => {
  const html = renderToStaticMarkup(createElement(WorkspaceSwitcher, {
    workspaces: workspaceOptions(fixture),
    activeWorkspace: {...fixture.organizations[0],membershipRole:"admin"},status:"ready",
  }));
  assert.match(html,/Admin · Organization/);
  assert.doesNotMatch(html,/HR Recruiter|HR Reviewer|HR Approver/);
});
