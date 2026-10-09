import {test,before,after} from "node:test";
import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {createHash} from "node:crypto";
import {createElement} from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {createServer} from "vite";
import {readiness} from "../src/utils/readiness.js";
import {validateResearchSample,loadResearchSample} from "../src/utils/researchSample.js";
import {organizationFeedback} from "../src/utils/organizationFeedback.js";
let server,SampleEvidence,HRJourney,resolveLiveUpdates;
before(async()=>{
  server=await createServer({root:new URL('../',import.meta.url).pathname,envDir:false,server:{middlewareMode:true,hmr:false,ws:false,watch:null},logLevel:'error'});
  ({SampleEvidence}=await server.ssrLoadModule('/src/components/dashboard/ResearchSample.jsx'));
  ({default:HRJourney}=await server.ssrLoadModule('/src/components/hiring/HRJourney.jsx'));
  ({liveUpdatesEnabled:resolveLiveUpdates}=await server.ssrLoadModule('/src/services/apiConfig.js'));
});
after(async()=>{await server?.close();});
const render=(Component,props)=>renderToStaticMarkup(createElement(Component,props));
async function report(){return JSON.parse(await readFile(new URL('../../docs/acceptance/phase10-fixture-report.json',import.meta.url),'utf8'));}
test('historical sample matches original bytes and pinned source checksum, with all 42 trials',async()=>{
  const original=await readFile(new URL('../../docs/acceptance/phase10-fixture-report.json',import.meta.url));
  const copy=await readFile(new URL('../public/examples/research-fixture-report.json',import.meta.url));
  assert.ok(original.equals(copy));
  const manifest=JSON.parse(await readFile(new URL('../public/examples/research-fixture-manifest.json',import.meta.url),'utf8'));
  assert.equal(manifest.sha256,createHash('sha256').update(copy).digest('hex'));
  assert.equal(validateResearchSample(JSON.parse(copy)).runEvidence.length,42);
});
test('sample rejects live or missing evidence and never offers mutation/human scoring',async()=>{
  const saved=await report();const html=render(SampleEvidence,{report:saved,onSelect(){}});
  assert.match(html,/Historical sample/);assert.match(html,/42 saved trials/);assert.match(html,/not a new experiment/);
  assert.doesNotMatch(html,/<form|Save human scores|Start.*trials/);
  const live=structuredClone(saved);live.observedEvidence.configuration.evidenceKind='provider_live';
  assert.throws(()=>validateResearchSample(live),/provenance/);
  const partial=structuredClone(saved);partial.runEvidence.pop();assert.throws(()=>validateResearchSample(partial),/provenance/);
});
test('sample loader uses only a static unauthenticated read, never a research admission endpoint',async()=>{
  const old=globalThis.fetch;const seen=[];const saved=await report();
  globalThis.fetch=async(url,options)=>{seen.push({url,options});return Response.json(saved);};
  try{await loadResearchSample(new AbortController().signal);assert.equal(seen.length,1);assert.equal(seen[0].url,'/examples/research-fixture-report.json');assert.equal(seen[0].options.credentials,'omit');}
  finally{globalThis.fetch=old;}
});
test('status stays Ready with polling, but failures and session changes are distinct',()=>{
  const base={backendStatus:'connected',workspaceStatus:'ready',dataStatus:'ready'};
  assert.equal(readiness(base).label,'Ready');assert.equal(readiness({...base,isRefreshing:true}).label,'Ready');
  assert.equal(readiness({...base,dataStatus:'loading'}).label,'Updating');
  assert.equal(readiness({...base,dataStatus:'error'}).label,'Connection problem');
  assert.equal(readiness({...base,authError:true}).label,'Sign in again');
});
test('socket requires an explicit opt-in and never treats a URL as permission',()=>{
  assert.equal(resolveLiveUpdates({}),false);assert.equal(resolveLiveUpdates({VITE_WS_URL:'wss://example.invalid'}),false);
  assert.equal(resolveLiveUpdates({VITE_LIVE_UPDATES_ENABLED:'false'}),false);assert.equal(resolveLiveUpdates({VITE_LIVE_UPDATES_ENABLED:'true'}),true);
});
test('private invitation errors are understandable without exposing code validity or raw server messages',()=>{
  for(const status of [400,404,409])assert.match(organizationFeedback({status,message:'PRIVATE-code'},'join'),/may be incorrect, already used, or revoked/);
  assert.doesNotMatch(organizationFeedback({status:404,message:'PRIVATE-code'},'join'),/PRIVATE/);
  assert.match(organizationFeedback({outcomeUnknown:true},'create'),/may already have saved/);
});
test('five-step hiring guide restricts authoring and cannot imply automatic approval',()=>{
  const snapshot={records:{requirements:[],'job-descriptions':[]},reviews:[],runs:[],agents:[],capabilities:{view:true},reviewCapabilities:{}};
  const html=render(HRJourney,{snapshot,onNavigate(){}});
  for(const text of ['1. Define','2. Create','3. Review','4. Submit','5. Record'])assert.ok(html.includes(text));
  assert.match(html,/Owner\/Admin access does not grant/);assert.match(html,/disabled=""/);assert.match(html,/read-only for drafting/);
});
