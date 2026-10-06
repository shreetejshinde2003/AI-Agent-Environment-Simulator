import {test, before, after} from "node:test";
import assert from "node:assert/strict";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {createServer} from "vite";
import {fileURLToPath} from "node:url";
import {reviewActions, reviewSubmission, matchingReviewRuns, reviewLabels} from "../src/utils/hrReviews.js";
const capabilities = {submit:true, recommend:true, approve:true, request_changes:true, reject:true};
const draft = {id:"JD-one", revision:2, content:{status:"draft", requirement:{id:"REQ-one",revision:1},roleKnowledge:null}};

test("review actions enforce state eligibility and never inherit stale approval", () => {
  assert.deepEqual(reviewActions({status:"pending_review"}, capabilities), ["recommend","request_changes","reject"]);
  assert.deepEqual(reviewActions({status:"reviewed"}, capabilities), ["approve","request_changes","reject"]);
  for (const status of ["approved","changes_requested","rejected"]) assert.deepEqual(reviewActions({status},capabilities),[]);
  assert.deepEqual(reviewActions({status:"reviewed",stale:true}, capabilities),[]);
});
test("reviewer and approver capabilities follow the existing separate HR role map", () => {
  assert.deepEqual(reviewActions({status:"pending_review"}, {recommend:true,request_changes:true}),["recommend","request_changes"]);
  assert.deepEqual(reviewActions({status:"reviewed"}, {recommend:true,request_changes:true}),[]);
  assert.deepEqual(reviewActions({status:"reviewed"}, {approve:true,reject:true}),["approve","reject"]);
  assert.deepEqual(reviewActions({status:"pending_review"}, {}),[]);
});
test("submission binds exact saved JD revision and optional original AI run IDs", () => {
  assert.deepEqual(reviewSubmission(draft,["HRRUN-original"]), {jobDescription:{id:"JD-one",revision:2},aiRunIds:["HRRUN-original"]});
  assert.throws(() => reviewSubmission(null));
  assert.throws(() => reviewSubmission({...draft,content:{status:"archived"}}));
});
test("AI association excludes failed, unrelated and outdated validation runs", () => {
  const request = {requirement:draft.content.requirement,roleKnowledge:null};
  const run = {id:"one",status:"completed",hrExecution:{request}};
  assert.deepEqual(matchingReviewRuns([run],draft),[run]);
  assert.deepEqual(matchingReviewRuns([{...run,status:"failed"}],draft),[]);
  assert.deepEqual(matchingReviewRuns([{...run,hrExecution:{request:{...request,jobDescription:{id:draft.id,revision:1}}}}],draft),[]);
  assert.deepEqual(matchingReviewRuns([{...run,hrExecution:{request:{...request,requirement:{id:"foreign",revision:1}}}}],draft),[]);
});
test("status labels distinguish review eligibility from final approval", () => {
  assert.equal(reviewLabels.reviewed,"Awaiting approval");assert.equal(reviewLabels.approved,"Approved");
  assert.equal(reviewLabels.changes_requested,"Changes requested");assert.equal(reviewLabels.rejected,"Rejected");
});
let server, client;
before(async () => {
  server=await createServer({root:fileURLToPath(new URL("../",import.meta.url)),envDir:false,
    define:{"import.meta.env.VITE_API_BASE_URL":JSON.stringify("http://fixture.invalid")},
    server:{middlewareMode:true,hmr:false,ws:false,watch:null},logLevel:"error"});
  ({apiClient:client}=await server.ssrLoadModule("/src/services/apiClient.js"));
});
after(async () => {await server?.close();});
test("review list detail history submission and decision use session and current workspace", async () => {
  const old=globalThis.fetch, calls=[];
  globalThis.fetch=async (url,options) => {calls.push({url,options});return {ok:true,json:async()=>({})};};
  try {
    await client.getHRReviewCapabilities("WS-a");await client.getHRReviews("WS-a");await client.getHRReview("HRR-a","WS-b");
    await client.getHRReviewHistory("HRR-a","WS-b");await client.submitHRReview(reviewSubmission(draft),"WS-a");
    await client.decideHRReview("HRR-a",{decision:"recommend",notes:"Human",expectedVersion:1},false,"WS-b");
    await client.decideHRReview("HRR-a",{decision:"approve",notes:"Human",expectedVersion:2},true,"WS-b");
    assert.deepEqual(calls.map(c=>c.url.replace("http://fixture.invalid/api/v1","")),[
      "/hiring/reviews/capabilities","/hiring/reviews","/hiring/reviews/HRR-a","/hiring/reviews/HRR-a/history","/hiring/reviews","/hiring/reviews/HRR-a/review","/hiring/reviews/HRR-a/approval"]);
    assert.deepEqual(calls.map(c=>c.options.headers["X-Workspace-Id"]),["WS-a","WS-a","WS-b","WS-b","WS-a","WS-b","WS-b"]);
    assert.ok(calls.every(c=>c.options.credentials==="include"));
    assert.equal(JSON.parse(calls[6].options.body).expectedVersion,2);
    assert.equal(JSON.parse(calls[4].options.body).jobDescription.revision,2);
  } finally {globalThis.fetch=old;}
});
test("conflicts and revoked authority remain visible API errors", async () => {
  const old=globalThis.fetch;
  try {
    for (const status of [409,403,404,401]) {
      globalThis.fetch=async()=>({ok:false,status,json:async()=>({detail:{code:"review_conflict",message:"Reload before deciding"}})});
      await assert.rejects(client.decideHRReview("HRR-a",{},true,"WS-a"), e=>e.status===status);
    }
  } finally {globalThis.fetch=old;}
});
test("review screen renders focused real workflow controls and proposal boundary", async () => {
  const {default:Component}=await server.ssrLoadModule("/src/components/hiring/HRReviews.jsx");
  const html=renderToStaticMarkup(React.createElement(Component,{workspaceId:"WS-a",records:{},onRevise:()=>{}}));
  assert.match(html,/Human review and approval/);assert.match(html,/AI suggestions remain proposals/);
  assert.match(html,/Reload review requests/);assert.match(html,/pending review and approval only/);
  assert.doesNotMatch(html,/Publish|Candidate screening/);
});
