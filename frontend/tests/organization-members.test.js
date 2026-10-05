import {after, before, test} from "node:test";
import assert from "node:assert/strict";
import {fileURLToPath} from "node:url";
import {createElement} from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {createServer} from "vite";

let server;
let OrganizationMembers;
let canViewOrganizationMembers;
let canChangeOrganizationRoles;
let organizationRoleLabel;

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
  ({
    canViewOrganizationMembers,
    canChangeOrganizationRoles,
    organizationRoleLabel,
  } = await server.ssrLoadModule("/src/utils/organizationMembers.js"));
});

after(async () => { await server?.close(); });

function renderFor(role, kind = "organization") {
  return renderToStaticMarkup(
    createElement(OrganizationMembers, {
      workspace: {
        id: kind === "organization" ? "WS-IICT" : "WS-personal",
        name: kind === "organization" ? "IICT" : "Personal Workspace",
        kind,
        membershipRole: kind === "organization" ? role : null,
      },
      onMembershipChanged: async () => {},
    }),
  );
}

test("member-management visibility follows centralized frontend role semantics", () => {
  assert.equal(canViewOrganizationMembers("owner"), true);
  assert.equal(canViewOrganizationMembers("admin"), true);
  assert.equal(canViewOrganizationMembers("member"), false);
  assert.equal(canViewOrganizationMembers("unknown"), false);

  assert.equal(canChangeOrganizationRoles("owner"), true);
  assert.equal(canChangeOrganizationRoles("admin"), false);
  assert.equal(canChangeOrganizationRoles("member"), false);

  assert.equal(organizationRoleLabel("owner"), "Owner");
  assert.equal(organizationRoleLabel("admin"), "Admin");
  assert.equal(organizationRoleLabel("member"), "Member");
});

test("member workspace does not expose management controls", () => {
  const html = renderFor("member");
  assert.match(html, /You are a Member of <strong>IICT<\/strong>/);
  assert.match(html, /available only to organization Owners and Admins/);
  assert.doesNotMatch(html, /<select/);
  assert.doesNotMatch(html, /Loading organization members/);
});

test("admin gets read-only member-management surface", () => {
  const html = renderFor("admin");
  assert.match(html, /Member management/);
  assert.match(html, /Admins can view members, manage HR responsibilities, and remove ordinary Members/);
  assert.match(html, /Owner\/Admin access changes remain owner-only/);
  assert.match(html, />Admin</);
  assert.doesNotMatch(html, /Owners can assign access roles, manage HR responsibilities, and remove members/);
});

test("owner gets role-management surface and Personal Workspace gets no org controls", () => {
  const ownerHtml = renderFor("owner");
  assert.match(ownerHtml, /Owners can assign access roles, manage HR responsibilities, and remove members/);
  assert.match(ownerHtml, /last active owner/);
  assert.match(ownerHtml, />Owner</);

  const personalHtml = renderFor(null, "personal");
  assert.match(personalHtml, /Select an organization workspace to manage its members/);
  assert.doesNotMatch(personalHtml, /Owners can assign/);
});
