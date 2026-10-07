export function measured(value, percent=false) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "Unknown";
  return percent ? `${(value*100).toFixed(1)}%` : Number(value.toFixed(3)).toString();
}
export function researchPayload(cases,modes,repetitions,purpose) {
  if (!cases.length || !modes.length || new Set(cases).size!==cases.length || new Set(modes).size!==modes.length || modes.some(m=>!["single","fixed","adaptive"].includes(m))) throw new Error("Select unique benchmarks and supported modes.");
  if (!Number.isInteger(repetitions)||repetitions<1||repetitions>5||cases.length*modes.length*repetitions>45) throw new Error("Use 1–5 repetitions and at most 45 runs.");
  if (!purpose.trim() || purpose.length>600) throw new Error("Enter a bounded experiment purpose.");
  return {benchmarkIds:cases,benchmarkVersion:"1",modes,repetitions,purpose:purpose.trim()};
}
export function scorePayload(run,task,scores,notes) {
  const dimensions=["correctness","relevance","completeness","clarity","groundedness","concision","sourceConsistency"];
  if (dimensions.some(d=>!Number.isInteger(scores[d])||scores[d]<1||scores[d]>5)||!notes.trim()||notes.length>2000) throw new Error("Score every dimension 1–5 and include a review rationale.");
  if (!task||task.id!==run.taskId||run.status!=="completed"||!run.outputSha256) throw new Error("Reload the completed output before scoring.");
  return {...Object.fromEntries(dimensions.map(d=>[d,scores[d]])),notes:notes.trim(),expectedOutputSha256:run.outputSha256,expectedReviewCount:task.humanReviews?.length??0};
}
