import { useCallback, useEffect, useState } from "react";
import { useSimulation } from "../../context/SimulationContext";
import AgentRelationshipGraph from "./AgentRelationshipGraph";
import RunPicker from "./RunPicker";
import SimulationTimeline from "./SimulationTimeline";
import WorkspaceInspector from "./WorkspaceInspector";
import { graphPath, modeLabel, runTitle } from "../../utils/runs";
import { hasRecordedTopology, recentRecordedEvents, resolveInspectorTarget } from "../../utils/workspaceSelection";
import "./WorkspaceShell.css";

// UI selection is scoped to a run ID. The graph and inspector read the current
// server snapshot rather than retaining copies of stages or route metadata.
export default function SimulationDetails({task}) {
  const {agents, tasks, selectTask, setActivePage, isLoading, error, socketStatus} = useSimulation();
  const [selection, setSelection] = useState({runId: null, target: null});
  useEffect(() => { setSelection({runId: task?.id ?? null, target: null}); }, [task?.id]);
  const target = resolveInspectorTarget(task, selection);
  const inspect = useCallback(next => setSelection({runId: task?.id ?? null, target: next}), [task?.id]);
  const recentEvents = recentRecordedEvents(task);
  return <div className="workbench-shell">
    <div className="workbench-grid">
      <aside className="workbench-runs" aria-labelledby="workbench-runs-title">
        <div className="workbench-pane-heading"><h2 id="workbench-runs-title">Runs</h2>
          <button type="button" className="text-button" onClick={() => setActivePage("task-summary")}>Full history</button></div>
        <RunPicker tasks={tasks} selectedTask={task} onSelect={selectTask}
          isLoading={isLoading} loadError={!!error && !tasks.length}/>
        <p className="muted">{tasks.length ? `${tasks.length} saved run${tasks.length === 1 ? "" : "s"}. Choose one to inspect its recorded path.` :
          isLoading ? "Loading saved runs…" : error ? "Run list unavailable." : "No simulation data yet."}</p>
        {task && <p className="workbench-run-id">ID: {task.id}</p>}
        <p className="muted">{socketStatus === "connected" ? "Live event connection active." :
          socketStatus === "connecting" ? "Live events reconnecting; REST refresh remains available." :
          "Live events offline; REST refresh remains available."}</p>
      </aside>
      <section className="workbench-flow" aria-labelledby="workbench-flow-title">
        <div className="workbench-pane-heading"><h2 id="workbench-flow-title">Execution flow</h2>
          {task?.routePlan && <button type="button" className="text-button"
            aria-pressed={target?.kind === "route"} onClick={() => inspect({kind: "route"})}>Inspect route decision</button>}</div>
        {task && <p className="muted">{runTitle(task)} · {modeLabel(task.executionMode)} · {task.status.replaceAll("_", " ")}</p>}
        {task && !hasRecordedTopology(task) ? <p className="empty-note">Stage topology was not recorded for this run. Its saved result and events remain available in the inspector and log.</p> :
          <AgentRelationshipGraph task={task} agents={agents} selectedTarget={target} onInspect={inspect}/>}
        {hasRecordedTopology(task) && <div className="workbench-path" aria-label="Recorded stage path">
          <strong>Recorded path</strong><p>{graphPath(task).map(id => id === "goal" ? "Goal" : id === "result" ? "Result" :
            id === "orchestrator" ? "Coordinator (no model call)" : agents.find(agent => agent.id === id)?.name ?? id).join(" → ")}</p>
        </div>}
      </section>
      <WorkspaceInspector task={task} target={target} agents={agents} onShowRun={() => inspect(null)}/>
    </div>
    <section className="workbench-events" aria-labelledby="workbench-events-title">
      <div className="workbench-pane-heading"><h2 id="workbench-events-title">Recent recorded events</h2>
        {task && <button type="button" className="text-button" onClick={() => setActivePage("logs")}>Open full execution log</button>}</div>
      <SimulationTimeline timeline={recentEvents}/>
      {task && <p className="muted">{task.events.length} recorded events · {task.messages.length} handoffs · {task.activities.length} activities.
        Events are saved backend records, not simulated playback.</p>}
    </section>
  </div>;
}
