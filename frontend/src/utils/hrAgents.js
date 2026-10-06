export function hrAgentPayload(agentId, requirement, knowledge, draft) {
  if (agentId === "hr_draft_validation") {
    if (!draft?.content?.requirement) throw new Error("Choose a saved description revision.");
    return {agentId, requirement: draft.content.requirement, roleKnowledge: draft.content.roleKnowledge ?? null,
      jobDescription: {id: draft.id, revision: draft.revision}};
  }
  if (!requirement?.id || !Number.isInteger(requirement.revision)) throw new Error("Choose a requirement revision.");
  return {agentId, requirement: {id: requirement.id, revision: requirement.revision},
    roleKnowledge: knowledge ? {id: knowledge.id, revision: knowledge.revision} : null};
}
export const hrRunPending = task => ["queued", "in_progress"].includes(task?.status);
export function hrStructuredOutput(task) {
  if (task?.status !== "completed" || !task.output) return null;
  return JSON.parse(task.output);
}
