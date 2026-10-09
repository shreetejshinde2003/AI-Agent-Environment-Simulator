import {useEffect, useRef, useState, useCallback} from "react";
import {apiClient} from "../../services/apiClient";
import Button from "../common/Button";
import Modal from "../common/Modal";
import Card from "../common/Card";
import {reviewActions, reviewLabels, reviewSubmission, matchingReviewRuns} from "../../utils/hrReviews";
import {hiringLabels} from "../../utils/hiring";
import {hrStructuredOutput} from "../../utils/hrAgents";
import "./HRReviews.css";

const actionLabels = {recommend:"Recommend for approval", request_changes:"Request changes", reject:"Reject", approve:"Approve"};
const noop = () => {};

function Snapshot({record, label}) {
  if (!record) return null;
  return <details open={label === "Submitted job description"}><summary>{label} · revision {record.revision}</summary>
    <p>{record.id} · edited by {record.updatedByUserId} · {new Date(record.updatedAt).toLocaleString()}</p>
    <dl>{Object.entries(record.content).map(([key, value]) => <div key={key}><dt>{hiringLabels[key] ?? key}</dt>
      <dd>{Array.isArray(value) ? value.join("; ") : value && typeof value === "object" ? `${value.id} · revision ${value.revision}` : String(value ?? "None")}</dd></div>)}</dl>
  </details>;
}
export default function HRReviews({workspaceId, records, onRevise, snapshot, focus, onChanged = noop}) {
  const [items, setItems] = useState([]), [capabilities, setCapabilities] = useState({});
  const [draftId, setDraftId] = useState(""), [runs, setRuns] = useState([]), [aiIds, setAiIds] = useState([]);
  const [selected, setSelected] = useState(null), [decision, setDecision] = useState(""), [notes, setNotes] = useState("");
  const [error, setError] = useState(""), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0), [pendingOnly, setPendingOnly] = useState(false);
  const [confirmation, setConfirmation] = useState(null);
  const generation = useRef(0);
  useEffect(() => {
    const invalidate = () => {generation.current++;};
    const requestId = ++generation.current;
    const controller = new AbortController();
    setItems([]); setRuns([]); setCapabilities({});
    setLoading(true); setError("");
    (async () => {
      const [list, permissions, evidence] = snapshot ? [snapshot.reviews, snapshot.reviewCapabilities, snapshot.runs] : await Promise.all([
        apiClient.getHRReviews(workspaceId, controller.signal), apiClient.getHRReviewCapabilities(workspaceId), apiClient.getHRRuns(workspaceId)]);
      if (generation.current !== requestId) return;
      setItems(list); setCapabilities(permissions); setRuns(evidence);
      setSelected(previous => previous ? list.find(item => item.id === previous.id) ?? null : null);
    })().catch(e => {if (generation.current === requestId) {setError(e.message); if ([401,403,404].includes(e.status)) onChanged();}})
      .finally(() => {if (generation.current === requestId) setLoading(false);});
    return () => {invalidate(); controller.abort();};
  }, [workspaceId, reload, records, snapshot, onChanged]);
  const drafts = (records["job-descriptions"] ?? []).filter(draft => draft.content.status === "draft");
  const draft = drafts.find(record => record.id === draftId);
  useEffect(() => {setAiIds([]);}, [draft?.id, draft?.revision]);
  const actions = reviewActions(selected, capabilities);
  const availableRuns = matchingReviewRuns(runs, draft);
  const open = useCallback(async id => {
    const requestId = ++generation.current;
    setSelected(null); setDecision(""); setNotes(""); setError(""); setBusy(true);
    try {
      const record = await apiClient.getHRReview(id, workspaceId);
      if (generation.current === requestId) setSelected(record);
    } catch (e) {if (generation.current === requestId) {setError(e.message); if ([401,403,404].includes(e.status)) onChanged();}}
    finally {if (generation.current === requestId) setBusy(false);}
  }, [workspaceId, onChanged]);
  useEffect(() => {
    if (!focus) return;
    if (focus.draftId) {setDraftId(focus.draftId); setAiIds([]);}
    if (focus.submissionId) open(focus.submissionId);
  }, [focus, open]);
  const submit = async event => {
    event.preventDefault(); setBusy(true); setError("");
    const requestId = generation.current;
    try {
      const record = await apiClient.submitHRReview(reviewSubmission(draft, aiIds), workspaceId);
      const list = await apiClient.getHRReviews(workspaceId);
      if (generation.current !== requestId) return;
      setItems(list); setSelected(record); setAiIds([]); setDecision(""); setNotes(""); onChanged();
    } catch (e) {if (generation.current === requestId) {setError(e.status === 409 ? `${e.message} Reload the review requests.` : e.message); if ([401,403,404].includes(e.status)) {setConfirmation(null); onChanged();}}}
    finally {if (generation.current === requestId) setBusy(false);}
  };
  const decide = async event => {
    event.preventDefault();
    setConfirmation({record:selected, decision, notes});
  };
  const confirmDecision = async () => {
    const {record:submitted, decision:confirmedDecision, notes:confirmedNotes} = confirmation;
    setBusy(true); setError("");
    const requestId = generation.current;
    try {
      const record = await apiClient.decideHRReview(submitted.id, {expectedVersion:submitted.version, decision:confirmedDecision, notes:confirmedNotes},
        submitted.status === "reviewed", workspaceId);
      if (generation.current !== requestId) return;
      setConfirmation(null); setSelected(record); setItems(list => list.map(item => item.id === record.id ? record : item)); setDecision(""); setNotes(""); onChanged();
    } catch (e) {if (generation.current === requestId) {setError(e.status === 409 ? `${e.message} Reload the review requests.` : e.message); if ([401,403,404].includes(e.status)) {setConfirmation(null); onChanged();}}}
    finally {if (generation.current === requestId) setBusy(false);}
  };
  return <Card title="Human review and approval" className="hr-reviews">
    <p>Submit a saved revision for an authenticated human decision. AI suggestions remain proposals. Editing a JD requires a new submission.</p>
    {loading && <p role="status">Loading review requests…</p>}
    {error && <p role="alert" className="run-error">{error}</p>}
    <Button type="button" disabled={busy} onClick={() => {setBusy(false); if (snapshot) onChanged(); else setReload(v => v + 1);}}>Reload review requests</Button>
    {capabilities.submit && <form onSubmit={submit} className="hiring-form">
      <label>Draft to submit<select aria-label="Draft to submit" required value={draftId} disabled={busy || loading} onChange={e => {setDraftId(e.target.value); setAiIds([]);}}>
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
    {confirmation && <Modal title="Confirm human decision" onClose={() => setConfirmation(null)} canDismiss={!busy}>
      <p>{actionLabels[confirmation.decision]} · JD revision {confirmation.record.jobDescription.revision}</p>
      <p>{confirmation.record.jobDescription.content.title} · submission {confirmation.record.id}</p>
      <p>{confirmation.notes}</p><p>This decision is permanent and applies only to this submitted revision.</p>
      {error && <p role="alert">{error}</p>}
      <Button disabled={busy} onClick={() => setConfirmation(null)}>Cancel</Button>{" "}
      <Button variant="primary" disabled={busy} onClick={confirmDecision}>{busy ? "Recording…" : "Confirm decision"}</Button>
    </Modal>}
    {selected && <article><h4>{reviewLabels[selected.status]} · revision {selected.jobDescription.revision}</h4>
      <details><summary>Submission metadata</summary><p>{selected.id}<br/>Submitted by {selected.requestedByUserId} · {new Date(selected.submittedAt).toLocaleString()}</p></details>
      {selected.stale && <p role="status">The JD has changed. This historical decision applies only to its submitted revision; further decisions are blocked.</p>}
      <Snapshot record={selected.jobDescription} label="Submitted job description"/>
      <Snapshot record={selected.requirement} label="Pinned requirement"/>
      <Snapshot record={selected.roleKnowledge} label="Pinned role knowledge"/>
      {!!selected.aiRunIds.length && <details><summary>Associated AI proposals</summary>{selected.aiRunIds.map(id => {
        const run = runs.find(item => item.id === id);
        return <div key={id}><p>{id} · {run?.assignedAgentId ?? "Unavailable evidence"}</p>{run ? <pre>{JSON.stringify({sources:run.hrExecution.sources, proposal:hrStructuredOutput(run)}, null, 2)}</pre> : <p>This AI run is unavailable in the current history. Check Recycle Bin or ask the workspace Owner; it may have been removed or become inaccessible.</p>}</div>;
      })}</details>}
      {!!actions.length && <form onSubmit={decide} className="hiring-form"><label>Human decision<select aria-label="Human decision" required disabled={busy} value={decision} onChange={e => setDecision(e.target.value)}>
        <option value="">Choose decision</option>{actions.map(action => <option key={action} value={action}>{actionLabels[action]}</option>)}</select></label>
        <label>Decision notes<textarea required maxLength={4000} rows={3} disabled={busy} value={notes} onChange={e => setNotes(e.target.value)}/></label>
        <Button type="submit" variant="primary" disabled={busy || !actions.includes(decision) || !notes.trim()}>{busy ? "Recording…" : "Record human decision"}</Button>
      </form>}
      {capabilities.submit && ["changes_requested", "rejected"].includes(selected.status) && <Button type="button" disabled={busy} onClick={() => onRevise(selected.jobDescription.id)}>Revise authoritative draft</Button>}
      <h4>Decision history</h4><ol>{selected.history.map(event => <li key={event.id}><strong>{event.action.replaceAll("_", " ")}</strong> · {event.actorUserId} · {new Date(event.occurredAt).toLocaleString()}
        <p>{event.fromStatus} → {event.toStatus}{event.notes && <><br/>{event.notes}</>}</p></li>)}</ol>
    </article>}
  </Card>;
}
