// Inspector projections use saved evidence only. A handoff is not proof of the
// exact prompt a provider received; stage input bindings are not persisted.
export function stageEvidence(task, agentId) {
  const stages = task?.stages ?? [];
  const index = stages.findIndex(stage => stage.agentId === agentId);
  if (index < 0) return null;
  return {
    stage: stages[index],
    incoming: (task.messages ?? []).filter(message => message.toAgentId === agentId),
    outgoing: (task.messages ?? []).filter(message => message.fromAgentId === agentId),
    latestEvent: (task.events ?? []).filter(event => event.agentId === agentId).at(-1) ?? null,
    latestActivity: (task.activities ?? []).filter(activity => activity.agentId === agentId).at(-1) ?? null,
    unstartedDownstream: task.status === "failed" ? stages.slice(index + 1).filter(stage => stage.status === "waiting" && !stage.startedAt) : [],
  };
}

export function handoffEvidence(task, messageId) {
  return (task?.messages ?? []).find(message => message.id === messageId) ?? null;
}

export function recordedTokenCoverage(task) {
  const stages = task?.stages ?? [];
  const attempted = stages.filter(stage => stage.startedAt);
  const measured = attempted.filter(stage => Number.isFinite(stage.totalTokens));

  const attemptedCount = attempted.length;
  const measuredCount = measured.length;

  const coverage =
    attemptedCount === 0 || measuredCount === 0
      ? "unavailable"
      : measuredCount < attemptedCount
        ? "partial"
        : "complete";

  return {
    attempted: attemptedCount,
    measured: measuredCount,
    coverage,
    total: coverage === "complete"
      ? measured.reduce((sum, stage) => sum + stage.totalTokens, 0)
      : null,
  };
}

export function runEvidence(task) {
  if (!task) return null;
  const stages = task.stages ?? [];
  const messages = task.messages ?? [];
  return {
    stages, messages,
    tokens: recordedTokenCoverage(task),
    models: [...new Set(stages.map(stage => stage.model).filter(Boolean))],
    invocationCount: task.agentInvocationCount ?? stages.filter(stage => stage.startedAt).length,
    handoffCount: task.handoffCount ?? messages.length,
    startedAgentIds: stages.filter(stage => stage.startedAt).map(stage => stage.agentId),
    route: task.executionMode === "adaptive" ? task.routePlan ?? null : null,
    terminal: ["completed", "failed"].includes(task.status),
    finalStage: stages.at(-1) ?? null,
  };
}
export function shortHash(value) {
  if (!value) return null;
  return value.length > 16
    ? `${value.slice(0, 8)}…${value.slice(-8)}`
    : value;
}

export function researchProvenance(task) {
  if (!task?.provenance) return null;

  return {
    experimentProtocol: task.provenance.experimentProtocolVersion,
    inputFingerprint: task.provenance.inputFingerprint,
    configuredModel: task.provenance.configuredModel,
    provider: task.provenance.provider,
    promptProtocol: task.provenance.promptProtocolVersion,
    contractsVersion: task.provenance.contractsVersion,
    routerVersion: task.provenance.routerVersion,
    requestedTaskType: task.provenance.requestedTaskType,
    datasetId: task.provenance.datasetId,
    datasetChecksum: task.provenance.datasetChecksum,
    maxOutputTokens: task.provenance.maxOutputTokens,
  };
}
export function hasAvailableRunContext(task) {
  return !!task?.uploads?.length || !!task?.benchmarkContext;
}
