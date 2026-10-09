import { useCallback, useEffect, useMemo, useState } from "react";
import { useSimulation } from "../../context/SimulationContext";
import AgentRelationshipGraph from "./AgentRelationshipGraph";
import RunProgress from "./RunProgress";
import RunPicker from "./RunPicker";
import OutputViewer from "./OutputViewer";
import Messages from "../../pages/Messages";
import Logs from "../../pages/Logs";
import WorkspaceInspector from "./WorkspaceInspector";
import TaskDetailsPanel from "./TaskDetailsPanel";
import { modeLabel, runTitle } from "../../utils/runs";
import { canvasPath } from "../../utils/graphPresentation";
import { graphTarget, hasRecordedTopology, resolveInspectorTarget } from "../../utils/workspaceSelection";
import { selectedRecord, workspaceRecords } from "../../utils/eventRecords";
import "./WorkspaceShell.css";

// UI selection is scoped to a run ID. The graph and inspector read the current
// server snapshot rather than retaining copies of stages or route metadata.
export default function SimulationDetails({task}) {
  const {agents, tasks, selectTask, setActivePage, isLoading, error, executionView, setExecutionView} = useSimulation();
  const [graphOpen, setGraphOpen] = useState(false);
  const [selection, setSelection] = useState({runId: null, target: null});
  useEffect(() => { setSelection({runId: task?.id ?? null, target: null}); }, [task?.id]);
  const records = useMemo(() => workspaceRecords(task), [task]);
  const record = selectedRecord(task, selection, records);
  useEffect(() => {
    if (selection.runId === task?.id && selection.recordKey && !record)
      setSelection({runId: task?.id ?? null, target: null});
  }, [task?.id, selection.runId, selection.recordKey, record]);
  const target = resolveInspectorTarget(task, selection, records);
  const inspect = useCallback(next => {setSelection({runId: task?.id ?? null, target: next});setExecutionView(next?.kind === "stage" || next?.kind === "result" ? "output" : "technical");}, [task?.id, setExecutionView]);
  const inspectRecord = useCallback(key => setSelection({runId: task?.id ?? null, recordKey: key}), [task?.id]);
  return <div className="workbench-shell">
      <aside className="workbench-runs" aria-labelledby="workbench-runs-title">
        <div className="workbench-pane-heading"><h2 id="workbench-runs-title">Runs</h2>
          <button type="button" className="text-button" onClick={() => setActivePage("task-summary")}>Full history</button></div>
        <RunPicker tasks={tasks} selectedTask={task} onSelect={selectTask}
          isLoading={isLoading} loadError={!!error && !tasks.length}/>
        <p className="muted">{tasks.length ? `${tasks.length} saved run${tasks.length === 1 ? "" : "s"}. Choose one to inspect its recorded path.` :
          isLoading ? "Loading saved runs…" : error ? "Run list unavailable." : "No simulation data yet."}</p>
      </aside>
    <RunProgress task={task} agents={agents} onInspect={next => {setSelection({runId:task.id,target:next});setExecutionView("technical");}}/>

    {task && <div className="event-filters" role="group" aria-label="Run detail views">
      {["overview", "output", "handoffs", "events", "technical"].map(view => <button type="button" key={view}
        aria-pressed={executionView === view} onClick={() => setExecutionView(view)}>{view === "technical" ? "Technical details" : view[0].toUpperCase()+view.slice(1)}</button>)}
    </div>}
    <section className="run-reading-pane" aria-label="Selected run details">
      {executionView === "overview" && (task ? <><h2>Run overview</h2><p>{modeLabel(task.executionMode)} · {task.status.replaceAll("_", " ")}</p>
        <h3>Original request</h3><p className="output-text">{task.directive}</p><p>{task.stages?.filter(s=>s.status === "completed").length ?? 0} completed stages · {task.messages?.length ?? 0} recorded handoffs</p>
        <button onClick={()=>{setSelection({runId:task.id,target:{kind:"result"}});setExecutionView("output");}}>Read final answer</button></> : <p>Choose or create a run to see its results.</p>)}
      {executionView === "output" && <>
        {target?.kind === "stage" && task?.stages?.find(s=>s.agentId===target.id) ? <>
          <button onClick={()=>inspect({kind:"result"})}>Read final answer</button>
          <OutputViewer key={task.id+target.id} text={task.stages.find(s=>s.agentId===target.id).output} intermediate
            label={`Intermediate agent output · ${agents.find(a=>a.id===target.id)?.name ?? target.id}`} />
          <details><summary>Stage technical evidence</summary><WorkspaceInspector task={task} target={target} agents={agents}
            onShowRun={()=>inspect(null)} onInspect={inspect} onInspectRecord={inspectRecord}/></details>
        </> : <OutputViewer key={task?.id ?? "empty"} text={task?.output} directive={task?.directive} emptyMessage={!task ? "Create a simulation to see its final answer here. Enter a task and choose an execution mode to start." : task.status === "failed" ? "No final answer recorded. Review the failure or open the recorded stage evidence." : task.status === "completed" ? "No final answer was recorded for this completed run." : "The final answer will appear here when execution finishes."}
          contract={task?.stages?.find(s=>s.output===task.output&&s.outputContract)?.outputContract}/>}
        {task && <details><summary>Exports and recorded run metadata</summary><TaskDetailsPanel task={task} view="metadata"/></details>}
      </>}
      {executionView === "handoffs" && <Messages contextual/>}
      {executionView === "events" && <Logs contextual onInspectRecord={key=>{inspectRecord(key);setExecutionView("technical");}}/>}
      {executionView === "technical" && <WorkspaceInspector task={task} target={target} agents={agents} selectedRecord={record}
        onShowRun={()=>inspect(null)} onInspect={inspect} onInspectRecord={inspectRecord}/>}
    </section>
    {task && <details className="execution-flow-details" onToggle={event => setGraphOpen(event.currentTarget.open)}><summary>Execution flow and routing</summary>
      <section className="workbench-flow" aria-labelledby="workbench-flow-title">
        <div className="workbench-pane-heading"><h2 id="workbench-flow-title">Execution flow</h2>
          {task?.executionMode === "adaptive" && task.routePlan && <button type="button" className="text-button"
            aria-pressed={target?.kind === "route"} onClick={() => inspect({kind: "route"})}>Inspect route decision</button>}</div>
        {task && <p className="muted">{runTitle(task)} · {modeLabel(task.executionMode)} · {task.status.replaceAll("_", " ")}</p>}
        {task && !hasRecordedTopology(task) ? <p className="empty-note">Stage topology was not recorded for this run. Its saved result and events remain available in the inspector and log.</p> :
          graphOpen && <AgentRelationshipGraph task={task} agents={agents} selectedTarget={target} onInspect={inspect}/>}
        {hasRecordedTopology(task) && <div className="workbench-path" aria-label="Recorded stage path">
          <strong>Recorded path</strong><ol>{canvasPath(task).map(id =>
            <li key={id}><button type="button" className="text-button" onClick={() => inspect(graphTarget(id))}
              aria-pressed={target?.kind === id || (target?.kind === "stage" && target.id === id)}>
              {id === "goal" ? "Goal" : id === "result" ? "Final result" : id === "route" ? "Route decision (no model call)" :
                id === "orchestrator" ? "Coordinator (no model call)" : agents.find(agent => agent.id === id)?.name ?? id}
            </button></li>)}</ol>
        </div>}
      </section>    </details>}
  </div>;
}
