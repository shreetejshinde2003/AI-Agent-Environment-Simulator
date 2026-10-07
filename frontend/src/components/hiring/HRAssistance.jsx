import {useEffect, useState, useRef} from "react";
import {apiClient} from "../../services/apiClient";
import Button from "../common/Button";
import Card from "../common/Card";
import {hrAgentPayload, hrRunPending, hrStructuredOutput} from "../../utils/hrAgents";

const noop = () => {};

function RevisionPicker({label, kind, records = [], workspaceId, onSelect, optional = false, initialRecord}) {
  const [id, setId] = useState(initialRecord?.id ?? "");
  const [revisions, setRevisions] = useState([]);
  const [value, setValue] = useState(String(initialRecord?.revision ?? ""));
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    setRevisions([]); setError("");
    if (id) apiClient.getHiringRevisions(kind, id, workspaceId)
      .then(rows => {if (alive) {setRevisions(rows);}})
      .catch(e => {if (alive) setError(e.message);});
    return () => {alive = false;};
  }, [id, kind, workspaceId]);
  return <fieldset><legend>{label}</legend>
    <label>Record<select value={id} onChange={e => {setId(e.target.value); setValue(""); onSelect(e.target.value ? undefined : null);}}>
      <option value="">{optional ? "No organization knowledge" : "Choose record"}</option>
      {records.map(record => <option key={record.id} value={record.id}>{record.content.title}</option>)}
    </select></label>
    {id && <label>Exact revision<select value={value} onChange={e => {setValue(e.target.value); onSelect(revisions.find(r => r.revision === Number(e.target.value)));}}>
      <option value="">Choose revision</option>{value && !revisions.some(record => String(record.revision) === value) && <option value={value}>Revision {value} · loading saved source…</option>}{revisions.map(record => <option key={record.revision} value={record.revision}>Revision {record.revision} · {record.content.status}</option>)}
    </select></label>}
    {error && <p role="alert">{error}</p>}
  </fieldset>;
}

function Proposal({task, onNavigate}) {
  const output = hrStructuredOutput(task);
  return <article className="hr-assistance-result" aria-label="HR execution result">
    <h3>{task.title}</h3><p role="status">Execution status: {task.status}</p><p>Run: {task.id}</p>
    {task.error && <p role="alert">{task.error}</p>}
    {output && <><h4>AI-generated proposal · human review required</h4>
      {Object.entries(output).map(([field, value]) => <section key={field}><h4>{field.replace(/([A-Z])/g, " $1")}</h4>
        {Array.isArray(value) ? <ul>{value.map((item, i) => <li key={i}>{typeof item === "object" ?
          <><strong>{item.category}</strong> · {item.source}.{item.field}: {item.explanation}</> : item}</li>)}</ul> : <p>{value || "Unspecified"}</p>}
      </section>)}
    </>}
    <details><summary>Source provenance and execution evidence</summary>
      <p>Provider: {task.hrExecution.provider} · configured model: {task.hrExecution.model} · implementation: {task.hrExecution.implementationVersion}</p>
      <ul>{task.hrExecution.sources.map(source => <li key={source.kind}>{source.kind}: {source.id} · revision {source.revision}{onNavigate && <Button onClick={() => onNavigate({section:"record",kind:{requirement:"requirements",role_knowledge:"role-knowledge",job_description:"job-descriptions"}[source.kind],id:source.id,revision:source.revision})}>Inspect source revision</Button>}<br/>Fingerprint: {source.fingerprint}</li>)}</ul>
      {task.stages.map((stage, i) => <p key={i}>Stage: {stage.status} · response model: {stage.model ?? "Unavailable"} · input tokens: {stage.inputTokens ?? "Unavailable"} · output tokens: {stage.outputTokens ?? "Unavailable"} · total tokens: {stage.totalTokens ?? "Unavailable"}</p>)}
      <p>Created: {task.createdAt} · completed: {task.completedAt ?? "Pending"}</p>
    </details>
  </article>;
}

export default function HRAssistance({workspaceId, records, snapshot, focus, onNavigate, onChanged = noop}) {
  const alive = useRef(true);
  const [seed, setSeed] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [action, setAction] = useState("");
  const [requirement, setRequirement] = useState(null);
  const [knowledge, setKnowledge] = useState(null);
  const [draft, setDraft] = useState(null);
  const [runs, setRuns] = useState([]);
  const [task, setTask] = useState(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    alive.current = true;
    let current = true;
    (snapshot ? Promise.resolve([snapshot.agents, snapshot.runs]) : Promise.all([apiClient.getHRAgents(workspaceId), apiClient.getHRRuns(workspaceId)]))
      .then(([agents, history]) => {if (current) {setCatalog(agents); setRuns(history); setTask(previous => previous ? history.find(run => run.id === previous.id) ?? null : null);}})
      .catch(e => {if (current) setError(e.message);});
    return () => {current = false; alive.current = false;};
  }, [workspaceId, reload, snapshot]);
  useEffect(() => {
    if (!hrRunPending(task)) return;
    let current = true;
    const timer = setTimeout(() => {
      apiClient.getHRRun(task.id, workspaceId).then(next => {if (current) {
        setTask(next); setRuns(previous => [next, ...previous.filter(run => run.id !== next.id)]);
        if (!hrRunPending(next)) onChanged();
      }}).catch(e => {if (current) {setTask(null); setError(e.message); if ([401,403,404].includes(e.status)) onChanged();}});
    }, 1200);
    return () => {current = false; clearTimeout(timer);};
  }, [task, workspaceId, onChanged]);
  const focused = useRef(null);
  useEffect(() => {
    if (!focus || focused.current === focus) return;
    focused.current = focus;
    setError("");
    if (focus.runId) {setTask(snapshot?.runs.find(run => run.id === focus.runId) ?? null); return;}
    if (focus.action && (focus.draft || focus.requirement)) {
      setSeed(focus);
      setAction(focus.action); setDraft(focus.action === "hr_draft_validation" ? focus.draft : null);
      const ref = focus.draft?.content.requirement ?? focus.requirement, knowledgeRef = focus.draft?.content.roleKnowledge;
      // A reference suffices for the existing payload; the authoritative server binds exact snapshots.
      setRequirement(ref); setKnowledge(knowledgeRef ?? null);
    }
  }, [focus, snapshot]);
  const selectedAction = catalog.find(agent => agent.id === action);
  const submit = async event => {
    event.preventDefault(); setError(""); setSubmitting(true);
    try {
      const admitted = await apiClient.runHRAgent(hrAgentPayload(action, requirement, knowledge, draft), workspaceId);
      if (alive.current) {setTask(admitted); setRuns(previous => [admitted, ...previous]); onChanged();}
    } catch (e) {if (alive.current) {setError(e.message); if ([401,403,404].includes(e.status)) onChanged();}}
    finally {if (alive.current) setSubmitting(false);}
  };
  return <Card title="AI assistance">
    <p>AI outputs are proposals. Review the sources and suggestions before making any human decision. These actions preserve human-authored records.</p>
    {error && <p role="alert">{error} <Button type="button" onClick={() => {setError(""); if (snapshot) onChanged(); else setReload(v => v + 1);}}>Reload assistance</Button></p>}
    <form className="hiring-form" onSubmit={submit}>
      <label>HR agent action<select value={action} disabled={submitting} onChange={e => {setSeed(null); setAction(e.target.value); setRequirement(null); setKnowledge(null); setDraft(null);}}>
        <option value="">Choose action</option>{catalog.map(agent => <option key={agent.id} value={agent.id} disabled={!agent.canExecute}>{agent.title}{!agent.canExecute ? " (HR permission required)" : ""}</option>)}
      </select></label>
      {selectedAction && <p>{selectedAction.purpose}</p>}
      {seed?.action === action && seed.draft && <p>Selected saved JD revision {seed.draft.revision} · requirement revision {seed.draft.content.requirement.revision} · {seed.draft.content.roleKnowledge ? `knowledge revision ${seed.draft.content.roleKnowledge.revision}` : "no role knowledge"}. Choose other sources below to change this selection.</p>}
      {action && <div key={action + (seed?.token ?? "")}>{action === "hr_draft_validation" ?
        <><RevisionPicker label="Saved description" kind="job-descriptions" records={records["job-descriptions"]} workspaceId={workspaceId} initialRecord={seed?.draft} onSelect={setDraft}/>
          {draft && <p>Validation uses requirement {draft.content.requirement.id} revision {draft.content.requirement.revision}, and {draft.content.roleKnowledge ? `knowledge ${draft.content.roleKnowledge.id} revision ${draft.content.roleKnowledge.revision}` : "no role knowledge"}.</p>}</> :
        <><RevisionPicker label="Source requirement" kind="requirements" records={records.requirements} workspaceId={workspaceId} initialRecord={seed?.draft?.content.requirement ?? seed?.requirement} onSelect={setRequirement}/>
          <RevisionPicker label="Organization role knowledge" kind="role-knowledge" records={records["role-knowledge"]} workspaceId={workspaceId} initialRecord={seed?.draft?.content.roleKnowledge} optional onSelect={setKnowledge}/></>}
      </div>}
      <Button type="submit" variant="primary" disabled={!selectedAction?.canExecute || submitting || hrRunPending(task) || knowledge === undefined || (action === "hr_draft_validation" ? !draft : !requirement)}>
        {submitting ? "Submitting…" : hrRunPending(task) ? "Executing…" : "Run AI assistance"}
      </Button>
    </form>
    <label className="hiring-form">Persisted HR runs<select value={task?.id ?? ""} onChange={e => {setError(""); setTask(runs.find(run => run.id === e.target.value) ?? null);}}>
      <option value="">Choose run</option>{runs.map(run => <option key={run.id} value={run.id}>{run.assignedAgentId} · {run.status} · {run.id}</option>)}
    </select></label>
    {task && <Proposal task={task} onNavigate={onNavigate}/>}
    <p className="muted">Failures remain in run history. Submit a new run to retry; each submission may call the configured provider. No approval or publication is performed.</p>
  </Card>;
}
