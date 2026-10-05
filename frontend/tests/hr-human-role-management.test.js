import {after, before, test} from "node:test";
import assert from "node:assert/strict";
import {fileURLToPath} from "node:url";
import {createElement} from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {createServer} from "vite";

let server;
let OrganizationMembers;
let canManageHrHumanRoles;
let humanRoleLabel;
let humanRolesByUser;

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

  ({default: OrganizationMembers} =
    await server.ssrLoadModule("/src/components/organizations/OrganizationMembers.jsx"));
  ({canManageHrHumanRoles, humanRoleLabel, humanRolesByUser} =
    await server.ssrLoadModule("/src/utils/hrHumanRoles.js"));
});

after(async () => { await server?.close(); });

function renderFor(role) {
  return renderToStaticMarkup(
    createElement(OrganizationMembers, {
      workspace: {
        id: "WS-IICT",
        name: "IICT",
        kind: "organization",
        membershipRole: role,
      },
      onMembershipChanged: async () => {},
    }),
  );
}

test("HR-role labels and management access remain distinct from IAM roles", () => {
  assert.equal(canManageHrHumanRoles("owner"), true);
  assert.equal(canManageHrHumanRoles("admin"), true);
  assert.equal(canManageHrHumanRoles("member"), false);
  assert.equal(canManageHrHumanRoles("hr_recruiter"), false);

  assert.equal(humanRoleLabel("hr_recruiter"), "HR Recruiter");
  assert.equal(humanRoleLabel("hr_reviewer"), "HR Reviewer");
  assert.equal(humanRoleLabel("hr_approver"), "HR Approver");
});

test("human-role assignments group multiple responsibilities per member", () => {
  const grouped = humanRolesByUser([
    {userId: "USR-1", humanRole: "hr_recruiter"},
    {userId: "USR-1", humanRole: "hr_reviewer"},
    {userId: "USR-2", humanRole: "hr_approver"},
  ]);

  assert.deepEqual([...grouped.get("USR-1")].sort(), ["hr_recruiter", "hr_reviewer"]);
  assert.deepEqual([...grouped.get("USR-2")], ["hr_approver"]);
});

test("owner surface explicitly separates access roles from HR responsibilities", () => {
  const html = renderFor("owner");
  assert.match(html, /Access roles control organization permissions/);
  assert.match(html, /HR responsibilities are separate domain roles/);
  assert.match(html, /Owners can assign access roles, manage HR responsibilities, and remove members/);
});

test("admin surface can manage HR responsibilities without gaining owner access-role controls", () => {
  const html = renderFor("admin");
  assert.match(html, /Admins can view members, manage HR responsibilities, and remove ordinary Members/);
  assert.match(html, /Owner\/Admin access changes remain owner-only/);
  assert.doesNotMatch(html, /Owners can change access roles/);
});
