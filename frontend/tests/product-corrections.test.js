import {test, before, after} from "node:test";
import assert from "node:assert/strict";
import {createElement} from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {createServer} from "vite";
import {fileURLToPath} from "node:url";
import {readFile} from "node:fs/promises";
import {isLastOrganizationOwner} from "../src/utils/organizationMembers.js";
let server, Topbar;
before(async()=>{server=await createServer({root:fileURLToPath(new URL('../',import.meta.url)),envDir:false,server:{middlewareMode:true,hmr:false,ws:false,watch:null},logLevel:'error'});({default:Topbar}=await server.ssrLoadModule('/src/layout/Topbar.jsx'));});
after(async()=>{await server?.close();});
test('last-owner controls distinguish sole owner from members and transferable ownership',()=>{
  const owner={userId:'a',membershipRole:'owner'}, member={userId:'b',membershipRole:'member'};
  assert.equal(isLastOrganizationOwner(owner,[owner,member]),true);
  assert.equal(isLastOrganizationOwner(member,[owner,member]),false);
  assert.equal(isLastOrganizationOwner(owner,[owner,{...owner,userId:'c'}]),false);
});
for (const [backendStatus,workspaceStatus,socketStatus,label] of [
  ['connected','ready','connected','Ready'],['connected','ready','offline','Ready · automatic refresh'],
  ['error','ready','offline','Offline'],['connected','error','offline','Workspace unavailable'],
]) test(`readiness displays ${label} with truthful expanded diagnostics`,()=>{
  const html=renderToStaticMarkup(createElement(Topbar,{backendStatus,workspaceStatus,socketStatus}));
  assert.ok(html.includes(label));assert.match(html,/<details/);
  if(socketStatus==='offline') assert.match(html,/Live events offline/);
  if(backendStatus==='error') assert.match(html,/Backend unavailable/);
});
test('research entry exposes real configuration and empty history',async()=>{
  const page=await readFile(new URL('../src/pages/ResearchLab.jsx',import.meta.url),'utf8');
  assert.match(page,/<section className="research-new">/);assert.match(page,/Start a comparison/);
  assert.match(page,/No experiments yet/);assert.match(page,/registry.cases.map/);
});
test('permanent deletion requires typed confirmation and clearly includes evidence',async()=>{
  const page=await readFile(new URL('../src/components/common/ConfirmRecycleAction.jsx',import.meta.url),'utf8');
  assert.match(page,/confirmation !== "DELETE"/);assert.match(page,/all associated execution evidence/);
});
