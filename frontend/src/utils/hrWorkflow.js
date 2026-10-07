import {matchingReviewRuns, reviewActions, reviewLabels} from "./hrReviews.js";

// Read projections only: authority remains with the Phase 5–7 mutation APIs.
export function draftWorkflow(draft, reviews, runs, capabilities, currentRevision = draft.revision) {
  const history = reviews.filter(item => item.jobDescription.id === draft.id);
  const submission = history.find(item => item.jobDescription.revision === draft.revision);
  const evidence = matchingReviewRuns(runs, draft);
  const priorApprovals = history.filter(item => item.status === "approved" && item.jobDescription.revision < draft.revision);
  let status = submission ? reviewLabels[submission.status] : history.length ? "Needs new revision submission" : "JD draft";
  let next = null;
  if (draft.revision !== currentRevision) status += " · historical revision";
  if (draft.content.status === "archived") status = "Archived JD";
  else if (draft.revision !== currentRevision) next = null;
  else if (submission && !submission.stale) {
    if (reviewActions(submission, capabilities).length) next = {section:"reviews", label:submission.status === "reviewed" ? "Record approver decision" : "Review submitted revision", submissionId:submission.id};
    else if (["changes_requested", "rejected"].includes(submission.status) && capabilities.submit) next = {section:"record", label:"Revise and save a new revision"};
  } else if (!submission && capabilities.submit) next = {section:"reviews", label:"Submit saved revision for review", draftId:draft.id};
  return {status, next, submission, history, evidence, priorApprovals};
}

export function relatedDrafts(kind, record, drafts) {
  if (kind === "job-descriptions") return [record];
  const field = kind === "requirements" ? "requirement" : "roleKnowledge";
  return drafts.filter(draft => draft.content[field]?.id === record.id);
}

export function relatedRuns(kind, record, runs) {
  const field = {requirements:"requirement", "role-knowledge":"roleKnowledge", "job-descriptions":"jobDescription"}[kind];
  return runs.filter(run => {
    const request = run.hrExecution?.request;
    if (kind === "job-descriptions") {
      // Source-matched proposals are related evidence, never proof of adoption.
      return matchingReviewRuns([run], record).length || request?.jobDescription?.id === record.id;
    }
    return request?.[field]?.id === record.id;
  });
}

export async function loadHiringWorkspace(client, workspaceId, signal) {
  const capabilities = await client.getHiringCapabilities(workspaceId, signal);
  if (!capabilities.view) return {capabilities, records:{}, reviews:[], runs:[], agents:[], reviewCapabilities:{}};
  // Bound connection pressure: publish only after every scoped read succeeds.
  const [requirements, knowledge, drafts] = await Promise.all([
    client.getHiringRecords("requirements", workspaceId, signal), client.getHiringRecords("role-knowledge", workspaceId, signal),
    client.getHiringRecords("job-descriptions", workspaceId, signal),
  ]);
  const [reviews, runs] = await Promise.all([client.getHRReviews(workspaceId, signal), client.getHRRuns(workspaceId, signal)]);
  const [agents, reviewCapabilities] = await Promise.all([client.getHRAgents(workspaceId, signal), client.getHRReviewCapabilities(workspaceId, signal)]);
  return {capabilities, records:{requirements, "role-knowledge":knowledge, "job-descriptions":drafts}, reviews, runs, agents, reviewCapabilities};
}
