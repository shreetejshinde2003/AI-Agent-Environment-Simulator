import {useEffect, useRef, useState} from "react";
import {apiClient} from "../../services/apiClient";
import Button from "../common/Button";
import Card from "../common/Card";
import {reviewActions, reviewLabels, reviewSubmission, matchingReviewRuns} from "../../utils/hrReviews";
import {hiringLabels} from "../../utils/hiring";
import {hrStructuredOutput} from "../../utils/hrAgents";
import "./HRReviews.css";

const actionLabels = {recommend:"Recommend for approval", request_changes:"Request changes", reject:"Reject", approve:"Approve"};
function Snapshot({record, label}) {
  if (!record) return null;
  return <details open={label === "Submitted job description"}><summary>{label} · revision {record.revision}</summary>
    <p>{record.id} · edited by {record.updatedByUserId} · {new Date(record.updatedAt).toLocaleString()}</p>
    <dl>{Object.entries(record.content).map(([key, value]) => <div key={key}><dt>{hiringLabels[key] ?? key}</dt>
      <dd>{Array.isArray(value) ? value.join("; ") : value && typeof value === "object" ? `${value.id} · revision ${value.revision}` : String(value ?? "None")}</dd></div>)}</dl>
  </details>;
}
export default function HRReviews({workspaceId, records, onRevise}) {
  const [items, setItems] = useState([]), [capabilities, setCapabilities] = useState({});
  const [draftId, setDraftId] = useState(""), [runs, setRuns] = useState([]), [aiIds, setAiIds] = useState([]);
  const [selected, setSelected] = useState(null), [decision, setDecision] = useState(""), [notes, setNotes] = useState("");
  const [error, setError] = useState(""), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0), [pendingOnly, setPendingOnly] = useState(false);
  const generation = useRef(0);
  useEffect(() => {
    const invalidate = () => {generation.current++;};
    const requestId = ++generation.current;
    const controller = new AbortController();
    setLoading(true); setBusy(false); setError(""); setSelected(null); setDecision(""); setNotes(""); setAiIds([]);
    (async () => {
      const [list, permissions, evidence] = await Promise.all([
        apiClient.getHRReviews(workspaceId, controller.signal), apiClient.getHRReviewCapabilities(workspaceId), apiClient.getHRRuns(workspaceId)]);
      if (generation.current !== requestId) return;
      setItems(list); setCapabilities(permissions); setRuns(evidence);
    })().catch(e => {if (generation.current === requestId) setError(e.message);})
      .finally(() => {if (generation.current === requestId) setLoading(false);});
    return () => {invalidate(); controller.abort();};
  }, [workspaceId, reload, records]);
  const drafts = (records["job-descriptions"] ?? []).filter(draft => draft.content.status === "draft");
  const draft = drafts.find(record => record.id === draftId);
  const actions = reviewActions(selected, capabilities);
  const availableRuns = matchingReviewRuns(runs, draft);
  const open = async id => {
    const requestId = ++generation.current;
    setSelected(null); setDecision(""); setNotes(""); setError(""); setBusy(true);
    try {
      const record = await apiClient.getHRReview(id, workspaceId);
      if (generation.current === requestId) setSelected(record);
    } catch (e) {if (generation.current === requestId) setError(e.message);}
    finally {if (generation.current === requestId) setBusy(false);}
  };
  const submit = async event => {
    event.preventDefault(); setBusy(true); setError("");
    const requestId = generation.current;
    try {
      const record = await apiClient.submitHRReview(reviewSubmission(draft, aiIds), workspaceId);
      const list = await apiClient.getHRReviews(workspaceId);
      if (generation.current !== requestId) return;
      setItems(list); setSelected(record); setAiIds([]); setDecision(""); setNotes("");
    } catch (e) {if (generation.current === requestId) setError(e.status === 409 ? `${e.message} Reload the review requests.` : e.message);}
    finally {if (generation.current === requestId) setBusy(false);}
  };
  const decide = async event => {
    event.preventDefault(); setBusy(true); setError("");
    const requestId = generation.current;
    try {
      const record = await apiClient.decideHRReview(selected.id, {expectedVersion:selected.version, decision, notes},
        selected.status === "reviewed", workspaceId);
      if (generation.current !== requestId) return;
      setSelected(record); setItems(list => list.map(item => item.id === record.id ? record : item)); setDecision(""); setNotes("");
    } catch (e) {if (generation.current === requestId) setError(e.status === 409 ? `${e.message} Reload the review requests.` : e.message);}
    finally {if (generation.current === requestId) setBusy(false);}
  };
  return <Card title="Human review and approval" className="hr-reviews">
    <p>Submit a saved revision for an authenticated human decision. AI suggestions remain proposals. Editing a JD requires a new submission.</p>
    {loading && <p role="status">Loading review requests…</p>}
    {error && <p role="alert" className="run-error">{error}</p>}
    <Button type="button" disabled={busy} onClick={() => {setBusy(false); setReload(v => v + 1);}}>Reload review requests</Button>
    {capabilities.submit && <form onSubmit={submit} className="hiring-form">
      <label>Draft to submit<select required value={draftId} disabled={busy || loading} onChange={e => {setDraftId(e.target.value); setAiIds([]);}}>
        <option value="">Choose saved job description</option>{drafts.map(record => <option key={record.id} value={record.id}>{record.content.title} · revision {record.revision}</option>)}
      </select></label>
      {!!availableRuns.length && <fieldset><legend>Associate AI assistance (optional)</legend><p>Links retain original run evidence; they do not claim adoption or approval.</p>
        {availableRuns.map(run => <label key={run.id}><input type="checkbox" disabled={busy} checked={aiIds.includes(run.id)}
          onChange={e => setAiIds(ids => e.target.checked ? [...ids, run.id] : ids.filter(id => id !== run.id))}/>{run.assignedAgentId} · {run.id}</label>)}
      </fieldset>}
      <Button type="submit" variant="primary" disabled={busy || loading || !draft || items.some(item => item.jobDescription.id === draft.id && item.jobDescription.revision === draft.revision)}>Submit for review</Button>
    </form>}
    <label className="review-filter"><input type="checkbox" checked={pendingOnly} onChange={e => setPendingOnly(e.target.checked)}/> Show pending review and approval only</label>
    <ul className="hiring-records">{items.filter(item => !pendingOnly || ["pending_review", "reviewed"].includes(item.status)).map(item => <li key={item.id}>
      <Button type="button" disabled={busy} onClick={() => open(item.id)}>{item.jobDescription.content.title}
        <small>{reviewLabels[item.status]} · revision {item.jobDescription.revision}{item.stale ? " · superseded revision" : ""}</small></Button></li>)}</ul>
    {!loading && !items.length && <p>No review requests yet.</p>}
    {selected && <article><h4>{reviewLabels[selected.status]} · revision {selected.jobDescription.revision}</h4>
      <p>{selected.id}<br/>Submitted by {selected.requestedByUserId} · {new Date(selected.submittedAt).toLocaleString()}</p>
      {selected.stale && <p role="status">The JD has changed. This historical decision applies only to its submitted revision; further decisions are blocked.</p>}
      <Snapshot record={selected.jobDescription} label="Submitted job description"/>
      <Snapshot record={selected.requirement} label="Pinned requirement"/>
      <Snapshot record={selected.roleKnowledge} label="Pinned role knowledge"/>
      {!!selected.aiRunIds.length && <details><summary>Associated AI proposals</summary>{selected.aiRunIds.map(id => {
        const run = runs.find(item => item.id === id);
        return <div key={id}><p>{id} · {run?.assignedAgentId ?? "Retained evidence"}</p>{run ? <pre>{JSON.stringify({sources:run.hrExecution.sources, proposal:hrStructuredOutput(run)}, null, 2)}</pre> : <p>Evidence is retained. Restore the run from Recycle Bin to inspect it.</p>}</div>;
      })}</details>}
      {!!actions.length && <form onSubmit={decide} className="hiring-form"><label>Human decision<select required disabled={busy} value={decision} onChange={e => setDecision(e.target.value)}>
        <option value="">Choose decision</option>{actions.map(action => <option key={action} value={action}>{actionLabels[action]}</option>)}</select></label>
        <label>Decision notes<textarea required maxLength={4000} rows={3} disabled={busy} value={notes} onChange={e => setNotes(e.target.value)}/></label>
        <Button type="submit" variant="primary" disabled={busy || !decision || !notes.trim()}>{busy ? "Recording…" : "Record human decision"}</Button>
      </form>}
      {capabilities.submit && ["changes_requested", "rejected"].includes(selected.status) && <Button type="button" disabled={busy} onClick={() => onRevise(selected.jobDescription.id)}>Revise authoritative draft</Button>}
      <h4>Decision history</h4><ol>{selected.history.map(event => <li key={event.id}><strong>{event.action.replaceAll("_", " ")}</strong> · {event.actorUserId} · {new Date(event.occurredAt).toLocaleString()}
        <p>{event.fromStatus} → {event.toStatus}{event.notes && <><br/>{event.notes}</>}</p></li>)}</ol>
    </article>}
  </Card>;
}
