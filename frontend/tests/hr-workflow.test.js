import {test, before, after} from "node:test";
import assert from "node:assert/strict";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {createServer} from "vite";
import {fileURLToPath} from "node:url";
import {draftWorkflow, relatedDrafts, relatedRuns, loadHiringWorkspace} from "../src/utils/hrWorkflow.js";
const draft={id:"JD-one",revision:2,updatedByUserId:"human",updatedAt:"2026-10-07T00:00:00Z",content:{title:"Human JD",status:"draft",requirement:{id:"REQ-one",revision:1},roleKnowledge:{id:"KN-one",revision:3}}};
const review=(revision,status,stale=false)=>({id:`review-${revision}`,jobDescription:{...draft,revision},status,stale,history:[],submittedAt:draft.updatedAt,requestedByUserId:"recruiter"});
const recruiter={submit:true}, reviewer={recommend:true,request_changes:true}, approver={recommend:true,approve:true,reject:true};
const run={id:"AI-one",status:"completed",assignedAgentId:"hr_jd_draft",hrExecution:{request:{requirement:draft.content.requirement,roleKnowledge:draft.content.roleKnowledge},sources:[{kind:"requirement",id:"REQ-one",revision:1}]}};

test("current draft needs submission even when an earlier revision was approved",()=>{
 const flow=draftWorkflow(draft,[review(1,"approved",true)],[run],recruiter);
 assert.equal(flow.status,"Needs new revision submission");assert.equal(flow.next.draftId,draft.id);
 assert.equal(flow.priorApprovals[0].jobDescription.revision,1);assert.equal(flow.evidence.length,1);
});
for(const [name,caps,expected] of [["recruiter",recruiter,null],["reviewer",reviewer,"Review submitted revision"],["approver",approver,"Review submitted revision"],["combined",{...recruiter,...reviewer,...approver},"Review submitted revision"],["IAM only",{},null],["no HR role",{},null]]){
 test(`pending review next action respects ${name} authority`,()=>assert.equal(draftWorkflow(draft,[review(2,"pending_review")],[],caps).next?.label??null,expected));
}
test("awaiting approval is actionable only with approver authority",()=>{
 assert.equal(draftWorkflow(draft,[review(2,"reviewed")],[],reviewer).next,null);
 assert.equal(draftWorkflow(draft,[review(2,"reviewed")],[],approver).next.label,"Record approver decision");
});
test("terminal feedback requires human revision and terminal approval has no decision action",()=>{
 for(const status of ["changes_requested","rejected"]) assert.equal(draftWorkflow(draft,[review(2,status)],[],recruiter).next.section,"record");
 assert.equal(draftWorkflow(draft,[review(2,"approved")],[],{...recruiter,...approver}).next,null);
 assert.equal(draftWorkflow({...draft,content:{...draft.content,status:"archived"}},[],[],recruiter).next,null);
 assert.equal(draftWorkflow({...draft,revision:1},[],[],recruiter,2).next,null);
});
test("relationship traversal retains exact pinned revisions and includes failed historical evidence",()=>{
 assert.deepEqual(relatedDrafts("requirements",{id:"REQ-one"},[draft]),[draft]);
 assert.deepEqual(relatedDrafts("role-knowledge",{id:"KN-one"},[draft]),[draft]);
 const old={...draft,revision:1};assert.deepEqual(relatedDrafts("job-descriptions",old,[draft]),[old]);
 assert.deepEqual(relatedRuns("requirements",{id:"REQ-one"},[{...run,status:"failed"}]),[{...run,status:"failed"}]);
 const outdated={...run,hrExecution:{request:{...run.hrExecution.request,jobDescription:{id:draft.id,revision:1}}}};
 assert.deepEqual(relatedRuns("job-descriptions",draft,[outdated]),[outdated]);
 assert.deepEqual(draftWorkflow(draft,[],[outdated],recruiter).evidence,[]);
});
test("workspace read uses one scope and abort signal for every authoritative API",async()=>{
 const calls=[];const signal=new AbortController().signal;
 const client=new Proxy({}, {get:(_,name)=>(...args)=>{calls.push([name,...args]);return Promise.resolve(name==="getHiringCapabilities"?{view:true}:[]);}});
 await loadHiringWorkspace(client,"WS-one",signal);
 assert.equal(calls.length,8);assert.ok(calls.every(call=>call.at(-2)==="WS-one" && call.at(-1)===signal));
});
test("denied HR capability never fetches tenant records or evidence",async()=>{
 const client={getHiringCapabilities:async()=>({view:false})};
 const data=await loadHiringWorkspace(client,"WS-denied");assert.deepEqual(data.records,{});assert.deepEqual(data.runs,[]);
});
test("a partial workspace response fails rather than exposing a mixed snapshot",async()=>{
 const client=new Proxy({}, {get:(_,name)=>async()=>{if(name==="getHiringCapabilities")return {view:true};if(name==="getHRRuns")throw new Error("revoked");return [];}});
 await assert.rejects(loadHiringWorkspace(client,"WS-one"),/revoked/);
});
let server;
before(async()=>{server=await createServer({root:fileURLToPath(new URL("../",import.meta.url)),server:{middlewareMode:true,hmr:false,ws:false,watch:null},logLevel:"error"});});
after(async()=>await server?.close());
test("workflow renders source links original approval and AI proposal boundary with human attribution",async()=>{
 const {default:Component}=await server.ssrLoadModule("/src/components/hiring/HRWorkflow.jsx");
 const snapshot={records:{requirements:[],"job-descriptions":[draft]},reviews:[review(1,"approved",true)],runs:[run],agents:[],capabilities:{view:true},reviewCapabilities:recruiter};
 const html=renderToStaticMarkup(React.createElement(Component,{snapshot,onNavigate:()=>{}}));
 for(const pattern of [/Source requirement.*revision 1/,/Source role knowledge.*revision 3/,/Earlier approval applies only to revision 1/,/Next action: Submit saved revision/,/AI-generated evidence/,/Human editor: human/]) assert.match(html,pattern);
 assert.doesNotMatch(html,/Auto.adopt|Publish/);
});

test("historical approved JD inspection exposes that revision without new actions",()=>{
 const old={...draft,revision:1};
 const flow=draftWorkflow(old,[review(1,"approved",true)],[run],{...recruiter,...approver},2);
 assert.equal(flow.status,"Approved · historical revision");assert.equal(flow.next,null);
 assert.deepEqual(relatedDrafts("job-descriptions",old,[draft]),[old]);
});
test("a new revision after feedback requires its own submission",()=>{
 for(const status of ["changes_requested","rejected","pending_review","reviewed"]){
  const flow=draftWorkflow(draft,[review(1,status,true)],[],recruiter);
  assert.equal(flow.status,"Needs new revision submission");assert.equal(flow.next.draftId,draft.id);
 }
});

test("source inspection renders historical JD usage while allowing actions only on the current revision",async()=>{
 const {default:Component}=await server.ssrLoadModule("/src/components/hiring/HRWorkflow.jsx");
 const old={...draft,revision:1};
 const source={id:"REQ-one",revision:1,content:{status:"draft"}};
 const snapshot={records:{requirements:[source],"job-descriptions":[draft]},reviews:[review(1,"approved",true)],runs:[],agents:[],capabilities:{view:true},reviewCapabilities:recruiter};
 const html=renderToStaticMarkup(React.createElement(Component,{snapshot,record:source,kind:"requirements",linkedDrafts:[old,draft],onNavigate:()=>{}}));
 assert.match(html,/JDs using this exact source revision/);assert.match(html,/Approved · historical revision/);
 assert.equal((html.match(/Next action:/g)??[]).length,1);
});
test("historical source lookup sends exact revision authenticated workspace and cancellation",async()=>{
 const {apiClient}=await server.ssrLoadModule("/src/services/apiClient.js");
 const old=globalThis.fetch,calls=[],controller=new AbortController();
 globalThis.fetch=async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>[]};};
 try {
  await apiClient.getLinkedJobDescriptions("role-knowledge","KN-one",3,"WS-current",controller.signal);
  assert.ok(calls[0].url.endsWith("/hiring/role-knowledge/KN-one/revisions/3/job-descriptions"));
  assert.equal(calls[0].options.credentials,"include");assert.equal(calls[0].options.headers["X-Workspace-Id"],"WS-current");
  assert.equal(calls[0].options.signal,controller.signal);
 } finally {globalThis.fetch=old;}
});
