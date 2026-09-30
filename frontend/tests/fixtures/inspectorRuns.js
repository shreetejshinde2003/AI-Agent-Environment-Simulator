// Deterministic presentation fixtures only. These are not production/demo data
// and must never be loaded by the application or sent to a model provider.
const timestamp = second => `2026-09-30T10:00:${String(second).padStart(2, "0")}Z`;

export const fixtureAgents = [
  ["direct", "Direct Agent"], ["research", "Research Agent"], ["data", "Data Agent"],
  ["analysis", "Analysis Agent"], ["summarizer", "Summarizer Agent"], ["report", "Report Agent"],
].map(([id, name]) => ({id, name, role: id, status: "idle", color: "#818cf8", implemented: true}));

const outputKeys = {direct: "final_answer", research: "research_findings", data: "structured_data",
  analysis: "insights", summarizer: "summary", report: "final_report"};

const stage = (agentId, index) => ({
  agentId, outputKey: outputKeys[agentId], status: "completed", startedAt: timestamp(index * 3 + 1),
  completedAt: timestamp(index * 3 + 3), durationSeconds: 2, model: "fixture-model",
  inputTokens: 30, outputTokens: 10, totalTokens: 40,
  output: `Fixture ${agentId} output.\n\n- Recorded aggregate observation\n- Uncertainty retained`,
  error: null, inputError: null,
});

const makeRun = (id, executionMode, agentIds, title) => {
  const stages = agentIds.map(stage);
  const messages = stages.slice(0, -1).map((current, index) => ({
    id: `${id}-message-${index}`, simulationId: id, fromAgentId: current.agentId,
    toAgentId: stages[index + 1].agentId, kind: "response", outputKey: current.outputKey,
    content: current.output, timestamp: current.completedAt,
  }));
  return {
    id, simulationId: id, title, directive: "Fixture only: describe aggregate software test outcomes.",
    assignedAgentId: executionMode === "single" ? "direct" : executionMode === "single_agent" ? agentIds[0] : "orchestrator",
    executionMode, priority: "medium", status: "completed", startedAt: timestamp(0),
    durationSeconds: 0, createdAt: timestamp(0), executionStartedAt: timestamp(1),
    completedAt: stages.at(-1).completedAt, elapsedSeconds: agentIds.length * 3 - 1,
    progressPercent: 100, progressSteps: [], output: stages.at(-1).output, error: null,
    ownerId: null, stages, messages, activities: stages.map((item, index) => ({
      id: `${id}-activity-${index}`, simulationId: id, agentId: item.agentId,
      timestamp: item.completedAt, text: `Fixture activity: ${item.agentId} completed`,
    })), events: stages.flatMap((item, index) => [
      {id: `${id}-start-${index}`, type: "agent_started", agentId: item.agentId,
        timestamp: item.startedAt, text: `Fixture event: ${item.agentId} started`},
      {id: `${id}-complete-${index}`, type: "agent_completed", agentId: item.agentId,
        timestamp: item.completedAt, text: `Fixture event: ${item.agentId} completed`},
    ]), uploads: [], datasetId: null, datasetChecksum: null, taskType: null,
    benchmarkContext: null, inputError: null, routePlan: null,
    agentInvocationCount: stages.length, handoffCount: messages.length,
  };
};

export const adaptiveRun = makeRun("fixture-adaptive", "adaptive", ["data", "analysis", "report"], "Fixture · Adaptive aggregate report");
adaptiveRun.taskType = "structured_data_analysis";
adaptiveRun.routePlan = {
  routerVersion: "rules-v1", executionMode: "adaptive", taskType: "structured_data_analysis",
  selectedAgentIds: ["data", "analysis", "report"], skippedAgentIds: ["research", "summarizer"],
  requiredCapabilities: ["structure", "analyze", "report"], availableInputs: ["original_directive", "uploaded_context"],
  reasons: ["Fixture decision: structured context supplied; Data and Analysis selected; Report presents the result."],
  validationStatus: "valid", validationError: null,
};
adaptiveRun.events.unshift({id: "fixture-route-event", type: "route_planned", agentId: null,
  timestamp: timestamp(0), text: "Fixture route plan recorded"});
adaptiveRun.uploads = [{id: "fixture-upload", filename: "test-outcomes.csv", format: "csv", sizeBytes: 31,
  createdAt: timestamp(0), preview: "suite,passed\nunit,12\nintegration,4", preparedContext: "suite,passed\nunit,12\nintegration,4",
  truncated: false, rowCount: 2, columns: ["suite", "passed"]}];

export const singleRun = makeRun("fixture-single", "single", ["direct"], "Fixture · Single direct answer");
export const fixedRun = makeRun("fixture-fixed", "fixed", ["research", "data", "analysis", "summarizer", "report"], "Fixture · Fixed five-stage run");
export const legacyRun = makeRun("fixture-legacy", "single_agent", ["research"], "Fixture · Individual research utility");

export const failedRun = structuredClone(adaptiveRun);
failedRun.id = failedRun.simulationId = "fixture-failed";
failedRun.title = "Fixture · Failed Analysis stage";
failedRun.status = "failed";
failedRun.output = null;
failedRun.error = "Fixture missing required context";
failedRun.progressPercent = 33;
failedRun.agentInvocationCount = 2;
failedRun.handoffCount = 1;
failedRun.messages = failedRun.messages.slice(0, 1);
failedRun.messages.forEach(message => {message.simulationId = failedRun.id;});
failedRun.stages[1] = {...failedRun.stages[1], status: "failed", output: null,
  model: null, inputTokens: null, outputTokens: null, totalTokens: null,
  error: failedRun.error, inputError: {code: "missing_required_input", agentId: "analysis", missingInputs: ["structured_data"]}};
failedRun.stages[2] = {...failedRun.stages[2], status: "waiting", startedAt: null, completedAt: null,
  durationSeconds: null, model: null, inputTokens: null, outputTokens: null, totalTokens: null, output: null};
failedRun.completedAt = failedRun.stages[1].completedAt;
failedRun.elapsedSeconds = 5;
failedRun.activities = failedRun.activities.slice(0, 1);
failedRun.activities.forEach(activity => {activity.simulationId = failedRun.id;});
failedRun.events = failedRun.events.filter(event =>
  event.agentId !== "report" && (event.type !== "agent_completed" || event.agentId === "data"));
failedRun.events.push({id: "fixture-failure-event", type: "agent_failed", agentId: "analysis",
  timestamp: failedRun.completedAt, text: failedRun.error});

export const unsafeLookingText = "<script>globalThis.fixtureExecuted = true</script>\n<img src=x onerror=alert(1)>\n\n# Fixture heading\n- Selectable text\n";
export const longRun = structuredClone(singleRun);
longRun.id = longRun.simulationId = "fixture-long";
longRun.title = "Fixture · Long recorded output";
longRun.output = unsafeLookingText + "Fixture paragraph with a preserved line break.\n\n".repeat(120);
longRun.stages[0].output = longRun.output;

export const inspectorRuns = [adaptiveRun, singleRun, fixedRun, legacyRun, failedRun, longRun];
