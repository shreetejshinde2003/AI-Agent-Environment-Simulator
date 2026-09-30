import {adaptiveRun} from "./inspectorRuns.js";

// Authoritative fixture snapshots, advanced explicitly by a local test harness.
// No production import, timers, provider calls or synthetic application events.
export const liveRunSnapshots = Array.from({length: 5}, (_, phase) => {
  const run = structuredClone(adaptiveRun);
  run.id = run.simulationId = "fixture-live";
  run.title = "Fixture · Live recorded transitions";
  const completed = Math.max(0, phase - 1);
  run.status = phase === 0 ? "queued" : phase === 4 ? "completed" : "in_progress";
  run.executionStartedAt = phase ? adaptiveRun.executionStartedAt : null;
  run.completedAt = phase === 4 ? adaptiveRun.completedAt : null;
  run.elapsedSeconds = phase === 4 ? adaptiveRun.elapsedSeconds : null;
  run.output = phase === 4 ? adaptiveRun.output : null;
  run.progressPercent = Math.floor(completed / 3 * 100);
  run.stages = run.stages.map((stage, index) => index < completed ? stage : {
    ...stage, status: phase && index === completed ? "active" : "waiting",
    startedAt: phase && index === completed ? stage.startedAt : null,
    completedAt: null, durationSeconds: null, output: null, model: null,
    inputTokens: null, outputTokens: null, totalTokens: null,
  });
  run.messages = run.messages.slice(0, Math.min(completed, 2));
  run.messages.forEach(message => {message.simulationId = run.id;});
  run.activities = run.activities.slice(0, completed);
  run.activities.forEach(activity => {activity.simulationId = run.id;});
  run.events = [{id: "live-created", type: "simulation_created", timestamp: run.createdAt, text: "Fixture run queued"},
    {...adaptiveRun.events[0], id: "live-route"}];
  if (phase) run.events.push({id: "live-started", type: "simulation_started", timestamp: run.executionStartedAt, text: "Fixture run started"});
  for (const stage of run.stages) {
    if (stage.startedAt) run.events.push({id: `live-start-${stage.agentId}`, type: "agent_started", agentId: stage.agentId,
      timestamp: stage.startedAt, text: `Fixture ${stage.agentId} started`});
    if (stage.completedAt) run.events.push({id: `live-complete-${stage.agentId}`, type: "agent_completed", agentId: stage.agentId,
      timestamp: stage.completedAt, text: `Fixture ${stage.agentId} completed`});
  }
  for (const message of run.messages) run.events.push({id: `live-message-${message.id}`, type: "message_created",
    agentId: message.fromAgentId, timestamp: message.timestamp, text: `Fixture ${message.fromAgentId} → ${message.toAgentId}`});
  if (phase === 4) run.events.push({id: "live-completed", type: "simulation_completed", timestamp: run.completedAt, text: "Fixture run completed"});
  run.events.sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
  run.agentInvocationCount = run.stages.filter(stage => stage.startedAt).length;
  run.handoffCount = run.messages.length;
  return run;
});

export const shortAdaptiveRun = structuredClone(adaptiveRun);
shortAdaptiveRun.id = shortAdaptiveRun.simulationId = "fixture-short";
shortAdaptiveRun.title = "Fixture · Short adaptive route";
shortAdaptiveRun.stages = shortAdaptiveRun.stages.slice(1);
shortAdaptiveRun.messages = shortAdaptiveRun.messages.slice(1);
shortAdaptiveRun.events = shortAdaptiveRun.events.filter(event => event.agentId !== "data");
shortAdaptiveRun.activities = shortAdaptiveRun.activities.filter(activity => activity.agentId !== "data");
shortAdaptiveRun.messages.forEach(message => {message.simulationId = shortAdaptiveRun.id;});
shortAdaptiveRun.activities.forEach(activity => {activity.simulationId = shortAdaptiveRun.id;});
shortAdaptiveRun.routePlan.selectedAgentIds = ["analysis", "report"];
shortAdaptiveRun.routePlan.skippedAgentIds = ["research", "data", "summarizer"];
shortAdaptiveRun.routePlan.requiredCapabilities = ["analyze", "report"];
shortAdaptiveRun.routePlan.reasons = ["Fixture decision: Analysis and Report selected for concise analysis and presentation."];
shortAdaptiveRun.agentInvocationCount = 2;
shortAdaptiveRun.handoffCount = 1;
shortAdaptiveRun.executionStartedAt = shortAdaptiveRun.stages[0].startedAt;
shortAdaptiveRun.elapsedSeconds = 5;
