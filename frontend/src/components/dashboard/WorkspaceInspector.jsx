import { useEffect, useRef } from "react";
import TaskDetailsPanel from "./TaskDetailsPanel";
import RecordedText from "./RecordedText";
import { stageView } from "../../utils/graphPresentation";
import {
  handoffEvidence,
  hasAvailableRunContext,
  recordedTokenCoverage,
  researchProvenance,
  shortHash,
  stageEvidence,
} from "../../utils/inspectorData";

const recorded = value => value == null ? "Not recorded" : value;
const time = value => value ? new Date(value).toLocaleString() : "Not recorded";
const duration = value => value == null ? "Not recorded" : `${value.toFixed(2)}s`;
const name = (id, agents) => agents.find(agent => agent.id === id)?.name ?? id;

function Metadata({items}) {
  return <dl className="metadata inspector-metadata">{items.filter(([, value]) => value != null).map(([label, value]) =>
    <div className="inspector-metadata-row" key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>;
}
function ResearchEvidence({task}) {
  const provenance = researchProvenance(task);
  const tokens = recordedTokenCoverage(task);

  if (!provenance) {
    return <section aria-labelledby="inspector-research-heading">
      <h4 id="inspector-research-heading">Research provenance</h4>
      <p className="muted">
        No experiment provenance was recorded for this run. Historical or utility runs may predate the experiment protocol.
      </p>
    </section>;
  }

  const coverageLabel =
    tokens.coverage === "complete"
      ? `Complete · ${tokens.measured}/${tokens.attempted} stages`
      : tokens.coverage === "partial"
        ? `Partial · ${tokens.measured}/${tokens.attempted} stages`
        : `Unavailable · ${tokens.measured}/${tokens.attempted} stages`;

  return <section aria-labelledby="inspector-research-heading">
    <h4 id="inspector-research-heading">Research provenance</h4>

    <Metadata items={[
      ["Experiment protocol", <code key="experiment-protocol">{provenance.experimentProtocol}</code>],
      ["Input fingerprint", provenance.inputFingerprint
        ? <code key="input-fingerprint" title={provenance.inputFingerprint}>
            {shortHash(provenance.inputFingerprint)}
          </code>
        : null],
      ["Provider", provenance.provider],
      ["Configured model", provenance.configuredModel
        ? <code key="configured-model">{provenance.configuredModel}</code>
        : null],
      ["Max output tokens", provenance.maxOutputTokens],
      ["Prompt protocol", provenance.promptProtocol
        ? <code key="prompt-protocol">{provenance.promptProtocol}</code>
        : null],
      ["Contracts version", provenance.contractsVersion
        ? <code key="contracts-version">{provenance.contractsVersion}</code>
        : null],
      ["Router version", provenance.routerVersion
        ? <code key="router-version">{provenance.routerVersion}</code>
        : "Not applicable"],
      ["Requested task type", provenance.requestedTaskType ?? "Not specified"],
      ["Dataset", provenance.datasetId ?? "None"],
      ["Dataset checksum", provenance.datasetChecksum
        ? <code key="dataset-checksum" title={provenance.datasetChecksum}>
            {shortHash(provenance.datasetChecksum)}
          </code>
        : "None"],
      ["Token coverage", coverageLabel],
      ["Comparable token total", tokens.total ?? "Not available"],
    ]}/>

    <p className="muted">
      The input fingerprint identifies matched research inputs. Execution mode is intentionally excluded from that fingerprint.
    </p>
  </section>;
}

function StageInspector({task, evidence, agents, onInspect, onInspectRecord}) {
  const {stage, incoming, outgoing, latestEvent, latestActivity, unstartedDownstream} = evidence;
  const roster = agents.find(agent => agent.id === stage.agentId);
  return <div className="workbench-inspector-content">
    <section aria-labelledby="inspector-agent-heading"><h4 id="inspector-agent-heading">Agent</h4>
      <Metadata items={[["Name", name(stage.agentId, agents)], ["Status", stageView(task, stage).text],
        ["Role", roster?.role], ["Model", stage.model ? <code key="model">{stage.model}</code> : null]]}/></section>
    <section aria-labelledby="inspector-execution-heading"><h4 id="inspector-execution-heading">Execution metadata</h4>
      <Metadata items={[["Started", time(stage.startedAt)], ["Completed", time(stage.completedAt)],
        ["Measured duration", duration(stage.durationSeconds)], ["Input tokens", recorded(stage.inputTokens)],
        ["Output tokens", recorded(stage.outputTokens)], ["Total tokens", recorded(stage.totalTokens)],
        ["Output key", <code key="output-key">{stage.outputKey}</code>]]}/>
      {latestEvent && <p className="inspector-event"><strong>Latest recorded event</strong><br/>
        <time dateTime={latestEvent.timestamp}>{time(latestEvent.timestamp)}</time> · {latestEvent.text}
        {onInspectRecord && <><br/><button type="button" className="text-button" onClick={() => onInspectRecord(`event:${latestEvent.id}`)}>Inspect latest event</button></>}</p>}
      {latestActivity && <p className="muted">Latest activity: {latestActivity.text}</p>}</section>
    <section aria-labelledby="inspector-input-heading"><h4 id="inspector-input-heading">Available run context</h4>
      <p className="muted">The exact model prompt and consumed input binding are not stored. These are recorded sources available to the run, not proof of what this stage consumed.</p>
      {task.directive && <details><summary>Original user directive</summary><RecordedText text={task.directive} label="user directive"/></details>}
      {incoming.length ? <><h5>Recorded upstream handoffs</h5><ul className="inspector-link-list">{incoming.map(message =>
        <li key={message.id}><button type="button" className="text-button" onClick={() => onInspect({kind: "handoff", id: message.id})}>
          {name(message.fromAgentId, agents)} → {name(message.toAgentId, agents)} · <code>{message.outputKey ?? message.kind}</code>
        </button></li>)}</ul></> : <p className="muted">No incoming handoff recorded for this stage.</p>}
      {hasAvailableRunContext(task) && <ul>{!!task.uploads?.length && <li>Uploaded references: {task.uploads.map(upload => upload.filename).join(", ")}</li>}
        {task.benchmarkContext && <li>Prepared, bounded benchmark context recorded for this run{task.datasetId ? ` (${task.datasetId})` : ""}</li>}</ul>}
    </section>
    {stage.status === "failed" && stage.inputError && <section aria-labelledby="inspector-input-error-heading"><h4 id="inspector-input-error-heading">Input contract failure</h4>
      <p className="run-error" role="alert"><code>{stage.inputError.code}</code>
        {stage.inputError.missingInputs?.length ? ` · Missing: ${stage.inputError.missingInputs.join(", ")}` : ""}</p></section>}
    {stage.status === "failed" && stage.error && <section aria-labelledby="inspector-error-heading"><h4 id="inspector-error-heading">Error</h4>
      <p className="run-error" role="alert">{stage.error}</p></section>}
    {unstartedDownstream.length > 0 && <p className="muted">Selected downstream stage{unstartedDownstream.length === 1 ? "" : "s"} not executed: {unstartedDownstream.map(item => name(item.agentId, agents)).join(", ")}.</p>}
    <section aria-labelledby="inspector-output-heading"><h4 id="inspector-output-heading">Recorded output</h4>
      {stage.output != null && <p className="muted">{stage.output.length.toLocaleString()} characters · <code>{stage.outputKey}</code></p>}
      <RecordedText text={stage.output} label="stage output"/></section>
    {outgoing.length > 0 && <section aria-labelledby="inspector-handoffs-heading"><h4 id="inspector-handoffs-heading">Outgoing handoffs</h4>
      <ul className="inspector-link-list">{outgoing.map(message => <li key={message.id}>
        <button type="button" className="text-button" onClick={() => onInspect({kind: "handoff", id: message.id})}>
          To {name(message.toAgentId, agents)} · <code>{message.outputKey ?? message.kind}</code> · <time dateTime={message.timestamp}>{time(message.timestamp)}</time>
        </button></li>)}</ul></section>}
  </div>;
}

function HandoffInspector({handoff, agents}) {
  return <div className="workbench-inspector-content">
    <section aria-labelledby="inspector-handoff-heading"><h4 id="inspector-handoff-heading">Recorded handoff</h4>
      <Metadata items={[["From", name(handoff.fromAgentId, agents)], ["To", name(handoff.toAgentId, agents)],
        ["Output key", handoff.outputKey ? <code key="output-key">{handoff.outputKey}</code> : null], ["Payload type", handoff.kind],
        ["Recorded", <time key="recorded" dateTime={handoff.timestamp}>{time(handoff.timestamp)}</time>],
        ["Characters", handoff.content == null ? "Not recorded" : handoff.content.length], ["Message ID", <code key="message-id">{handoff.id}</code>]]}/>
      <p className="muted">This persisted message records a handoff, not a delivery acknowledgement or the receiver’s exact model prompt.</p></section>
    <section aria-labelledby="inspector-handoff-content-heading"><h4 id="inspector-handoff-content-heading">Recorded content</h4>
      <RecordedText text={handoff.content} label="handoff content"/></section>
  </div>;
}

function RouteInspector({task, route, agents}) {
  const routeEvent = task.events?.find(event => event.type === "route_planned");
  return <div className="workbench-inspector-content">
    <section aria-labelledby="inspector-route-heading"><h4 id="inspector-route-heading">Rule-based decision</h4>
      <Metadata items={[["Router type", "Deterministic rules"], ["Router version", <code key="router-version">{route.routerVersion}</code>],
        ["Task type", route.taskType?.replaceAll("_", " ")],
        ["Required capabilities", route.requiredCapabilities?.length ? route.requiredCapabilities.join(", ") : "None recorded"],
        ["Available inputs", route.availableInputs?.length ? route.availableInputs.join(", ") : "None recorded"],
        ["Validation", route.validationStatus],
        ["Plan recorded", routeEvent ? <time key="plan-recorded" dateTime={routeEvent.timestamp}>{time(routeEvent.timestamp)}</time> : null]]}/></section>
    <section aria-labelledby="inspector-route-path-heading"><h4 id="inspector-route-path-heading">Selected route</h4>
      <p>{route.selectedAgentIds?.map(id => name(id, agents)).join(" → ") || "No selected agents recorded"}</p>
      <p className="muted">Not selected: {route.skippedAgentIds?.length ? route.skippedAgentIds.map(id => name(id, agents)).join(", ") : "None"}. These agents are outside the executed path.</p></section>
    <section aria-labelledby="inspector-route-reason-heading"><h4 id="inspector-route-reason-heading">Decision summary</h4>
      {route.reasons?.length ? <ul>{route.reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul> : <p className="muted">No decision summary recorded.</p>}
      {route.validationError && <p className="run-error" role="alert">{route.validationError}</p>}
      <p className="muted">This saved plan is not a model invocation or a private reasoning trace.</p></section>
  </div>;
}

function EventInspector({task, row, agents, onInspect}) {
  const {record, source} = row;
  const relatedStage = task.stages?.find(stage => stage.agentId === record.agentId);
  return <section className="inspector-event-record" aria-label="Recorded event details">
    <Metadata items={[["Record type", source === "event" ? record.type : "Agent activity"],
      ["Timestamp", time(record.timestamp)], ["Run ID", <code key="run-id">{task.id}</code>],
      ["Record ID", <code key="record-id">{record.id}</code>], ["Agent", record.agentId ? name(record.agentId, agents) : null]]}/>
    <RecordedText text={record.text} label="event detail"/>
    {source === "event" && record.type === "message_created" && <p className="muted">This event does not store a message ID. Its exact handoff cannot be identified from this record.</p>}
    {relatedStage && <button type="button" className="text-button" onClick={() => onInspect({kind: "stage", id: relatedStage.agentId})}>Inspect related agent: {name(relatedStage.agentId, agents)}</button>}
  </section>;
}

export default function WorkspaceInspector({task, target, agents = [], selectedRecord, onShowRun, onInspect = () => {}, onInspectRecord}) {
  const panel = useRef(null), heading = useRef(null), focusOnChange = useRef(false);
  useEffect(() => {
    if (panel.current) panel.current.scrollTop = 0;
    if (focusOnChange.current) heading.current?.focus({preventScroll: true});
    focusOnChange.current = false;
  }, [task?.id, target?.kind, target?.source, target?.id]);
  useEffect(() => {
    if (selectedRecord?.key) heading.current?.focus();
  }, [selectedRecord?.key]);
  function inspectRelated(next) { focusOnChange.current = true; onInspect(next); }
  function inspectRecord(key) { focusOnChange.current = true; onInspectRecord?.(key); }
  const evidence = target?.kind === "stage" ? stageEvidence(task, target.id) : null;
  const handoff = target?.kind === "handoff" ? handoffEvidence(task, target.id) : null;
  const route = target?.kind === "route" && task?.executionMode === "adaptive" ? task.routePlan : null;
  const eventRecord = target?.kind === "event" ? (target.source === "activity" ? task?.activities : task?.events)?.find(record => record.id === target.id) : null;
  const title = evidence ? `${name(evidence.stage.agentId, agents)} · ${stageView(task, evidence.stage).text}` :
    handoff ? `${name(handoff.fromAgentId, agents)} → ${name(handoff.toAgentId, agents)}` :
      route ? "Route decision · rule-based" : target?.kind === "goal" ? "User goal" :
        target?.kind === "orchestrator" ? "Sequential coordinator" :
          target?.kind === "result" ? "Final result" : eventRecord ? "Recorded event" : "Run overview";
  return <section ref={panel} className="workbench-inspector" aria-labelledby="workbench-inspector-title">
    <div className="workbench-pane-heading"><h2 id="workbench-inspector-title">Inspector</h2>
      {target && <button type="button" className="text-button" onClick={() => { focusOnChange.current = true; onShowRun(); }}>Run overview</button>}</div>
    <h3 ref={heading} tabIndex={-1} className="workbench-inspector-subtitle" aria-live="polite">{title}</h3>
    {selectedRecord && target?.kind !== "event" && <section className="inspector-event-record" aria-label="Selected record context">
      <h4>Selected record · {selectedRecord.label}</h4>
      <p><code>{selectedRecord.record.type ?? selectedRecord.record.kind ?? selectedRecord.source}</code> · <time dateTime={selectedRecord.record.timestamp}>{time(selectedRecord.record.timestamp)}</time> · <code>{selectedRecord.record.id}</code></p>
      <p className="muted">Run: <code>{task.id}</code></p>
      <p>{selectedRecord.record.text ?? `${selectedRecord.record.fromAgentId} → ${selectedRecord.record.toAgentId}`}</p>
    </section>}
    {!task ? <p className="empty-note">Choose a run to inspect its recorded execution.</p> :
      eventRecord ? <EventInspector task={task} row={{record: eventRecord, source: target.source}} agents={agents} onInspect={inspectRelated}/> :
      evidence ? <StageInspector key={`${task.id}:${evidence.stage.agentId}`} task={task} evidence={evidence} agents={agents} onInspect={inspectRelated} onInspectRecord={onInspectRecord ? inspectRecord : null}/> :
        handoff ? <HandoffInspector key={handoff.id} handoff={handoff} agents={agents}/> :
          route ? <RouteInspector task={task} route={route} agents={agents}/> :
            target?.kind === "goal" ? <RecordedText text={task.directive} label="user directive"/> :
              target?.kind === "orchestrator" ? <p>The fixed-mode coordinator runs the selected stages in order. It does not invoke a model itself.</p> :
                <>
  {target?.kind !== "result" && <ResearchEvidence task={task}/>}
  <TaskDetailsPanel
    key={task.id}
    task={task}
    view={target?.kind === "result" ? "result" : "overview"}
    onInspect={inspectRelated}
  />
</>}
  </section>;
}
