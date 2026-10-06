export const reviewLabels = {
  pending_review: "Pending review", reviewed: "Awaiting approval", changes_requested: "Changes requested",
  rejected: "Rejected", approved: "Approved",
};
export function reviewActions(record, capabilities) {
  if (!record || record.stale) return [];
  const actions = record.status === "pending_review" ? ["recommend", "request_changes", "reject"] :
    record.status === "reviewed" && capabilities.approve ? ["approve", "request_changes", "reject"] : [];
  return actions.filter(action => capabilities[action]);
}
export function reviewSubmission(draft, aiRunIds = []) {
  if (!draft || draft.content.status !== "draft") throw new Error("Choose a saved editable draft.");
  return {jobDescription: {id: draft.id, revision: draft.revision}, aiRunIds};
}
export function matchingReviewRuns(runs, draft) {
  if (!draft) return [];
  const same = (a, b) => (a?.id ?? null) === (b?.id ?? null) && (a?.revision ?? null) === (b?.revision ?? null);
  return runs.filter(run => {
    const source = run.hrExecution?.request;
    return run.status === "completed" && source && same(source.requirement, draft.content.requirement) &&
      same(source.roleKnowledge, draft.content.roleKnowledge) &&
      (!source.jobDescription || same(source.jobDescription, {id:draft.id, revision:draft.revision}));
  });
}
