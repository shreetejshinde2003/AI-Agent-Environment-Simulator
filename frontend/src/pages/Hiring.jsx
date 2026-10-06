import {useEffect, useState, useRef} from "react";
import {useWorkspace} from "../hooks/useWorkspace";
import {apiClient} from "../services/apiClient";
import Button from "../components/common/Button";
import Card from "../components/common/Card";
import {hiringKinds, hiringLabels, hiringForm, hiringPayload, hiringStatuses, listFields} from "../utils/hiring";
import "./Hiring.css";

function HiringWorkspace({workspaceId}) {
  const detailRequest = useRef(0);
  const [kind, setKind] = useState("requirements");
  const [records, setRecords] = useState({});
  const [capabilities, setCapabilities] = useState(null);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const invalidateDetails = () => {detailRequest.current++;};
    invalidateDetails();
    let alive = true;
    const controller = new AbortController();
    setLoading(true); setError(""); setForm(null); setSelected(null); setHistory([]);
    setRecords({}); setCapabilities(null);
    (async () => {
      const permissions = await apiClient.getHiringCapabilities(workspaceId);
      if (!alive) return;
      setCapabilities(permissions);
      if (!permissions.view) return;
      const groups = await Promise.all(hiringKinds.map(item => apiClient.getHiringRecords(item.key, workspaceId, controller.signal)));
      if (alive) setRecords(Object.fromEntries(hiringKinds.map((item, i) => [item.key, groups[i]])));
    })().catch(e => {if (alive) setError(e.message);}).finally(() => {if (alive) setLoading(false);});
    return () => {invalidateDetails(); alive = false; controller.abort();};
  }, [workspaceId, reload]);
  const definition = hiringKinds.find(item => item.key === kind);
  const canEdit = capabilities?.[kind.replaceAll("-", "_")] && selected?.content.status !== "archived";
  const switchKind = value => {detailRequest.current++; setKind(value); setSelected(null); setForm(null); setHistory([]); setError("");};
  const openRecord = async record => {
    const requestId = ++detailRequest.current;
    setSelected(record); setForm(hiringForm(kind, record.content)); setHistory([]); setError("");
    try {
      const revisions = await apiClient.getHiringRevisions(kind, record.id, workspaceId);
      if (requestId === detailRequest.current) setHistory(revisions);
    } catch (e) {if (requestId === detailRequest.current) setError(e.message);}
  };
  const save = async event => {
    event.preventDefault(); setSaving(true); setError("");
    try {
      const payload = hiringPayload(kind, form, selected?.revision);
      await apiClient.saveHiringRecord(kind, selected?.id, payload, workspaceId);
      setReload(value => value + 1);
    } catch (e) {setError(e.message);}
    finally {setSaving(false);}
  };
  const sourceSelect = (field, sourceKind, label, required) => {
    const available = records[sourceKind] ?? [];
    const current = form[field];
    const options = available.filter(record => !["closed", "archived"].includes(record.content.status))
      .map(record => ({value: `${record.id}@${record.revision}`, label: `${record.content.title} · revision ${record.revision}`}));
    if (current && !options.some(option => option.value === current)) {
      const [id, revision] = current.split("@");
      const source = available.find(record => record.id === id);
      options.push({value: current, label: `${source?.content.title ?? "Saved source"} · revision ${revision} (saved source)`});
    }
    return <label key={field}>{label}<select required={required} value={current} disabled={!canEdit || saving}
      onChange={e => setForm({...form, [field]: e.target.value})}>
      <option value="">{required ? "Choose requirement" : "No role knowledge"}</option>
      {options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select></label>;
  };
  return <div className="hiring-workspace">
    <p className="muted">Organization hiring requirements, private role knowledge and human-authored job description drafts.</p>
    {loading && <p role="status">Loading hiring records…</p>}
    {error && <p role="alert" className="run-error">{error} <Button type="button" disabled={saving} onClick={() => setReload(v => v + 1)}>Reload</Button></p>}
    {!loading && capabilities && !capabilities.view && <p role="status">An active HR Recruiter, Reviewer or Approver role is required. Manage assignments in Organizations.</p>}
    {!loading && capabilities?.view && <>
      <nav aria-label="Hiring sections" className="hiring-tabs">{hiringKinds.map(item => <Button type="button" key={item.key}
        aria-pressed={item.key === kind} disabled={saving} onClick={() => switchKind(item.key)}>{item.label}</Button>)}</nav>
      <div className="hiring-columns"><Card title={definition.label}>
        <Button type="button" disabled={!capabilities[kind.replaceAll("-", "_")] || saving} onClick={() => {detailRequest.current++; setSelected(null); setForm(hiringForm(kind)); setHistory([]); setError("");}}>Create {kind === "job-descriptions" ? "draft" : "record"}</Button>
        {!capabilities[kind.replaceAll("-", "_")] && <p className="muted">Read-only access. HR Recruiter permission is required to edit.</p>}
        {!records[kind]?.length && <p>No records yet.</p>}
        <ul className="hiring-records">{records[kind]?.map(record => <li key={record.id}><Button type="button" disabled={saving} onClick={() => openRecord(record)}>
          {record.content.title}<small>{record.content.status} · revision {record.revision}</small></Button></li>)}</ul>
      </Card><Card title={selected ? "Record details" : "New record"}>
        {!form && <p>Select a record or create one.</p>}
        {selected?.content.status === "archived" && <p className="muted">Archived record · read-only. Its revision history remains available.</p>}
        {form && <form onSubmit={save} className="hiring-form">
          {selected && <p className="muted">{selected.id}<br/>Created by {selected.createdByUserId} · {new Date(selected.createdAt).toLocaleString()}<br/>Updated by {selected.updatedByUserId} · {new Date(selected.updatedAt).toLocaleString()}</p>}
          {definition.fields.map(field => <label key={field}>{hiringLabels[field]}{listFields.has(field) && <small>One item per line</small>}
            {field === "openings" ? <input type="number" min="1" max="10000" step="1" required value={form[field]} disabled={!canEdit || saving} onChange={e => setForm({...form, [field]: e.target.value})}/> :
              <textarea rows={listFields.has(field) || ["purpose", "summary"].includes(field) ? 3 : 1}
                required={["title", "purpose", "summary"].includes(field)} maxLength={["title", "department", "location", "employmentArrangement"].includes(field) ? 200 : field === "summary" ? 8000 : listFields.has(field) ? undefined : 4000}
                value={form[field]} disabled={!canEdit || saving} onChange={e => setForm({...form, [field]: e.target.value})}/>}
          </label>)}
          {kind === "job-descriptions" && <>{sourceSelect("requirement", "requirements", "Source hiring requirement", true)}{sourceSelect("roleKnowledge", "role-knowledge", "Source role knowledge", false)}<p className="muted">Sources retain their selected revisions when the source records change.</p></>}
          <label>Lifecycle status<select value={form.status} disabled={!canEdit || saving || !selected} onChange={e => setForm({...form, status: e.target.value})}>
            {hiringStatuses(kind, selected?.content.status).map(value => <option key={value}>{value}</option>)}
          </select></label>
          <Button variant="primary" type="submit" disabled={!canEdit || saving}>{saving ? "Saving…" : "Save"}</Button>
        </form>}
        {!!history.length && <details><summary>Revision history ({history.length})</summary>{history.map(record => <article key={record.revision}><h3>Revision {record.revision} · {record.content.status}</h3><p>{record.updatedByUserId} · {new Date(record.updatedAt).toLocaleString()}</p><dl>{Object.entries(record.content).map(([key, value]) => <div key={key}><dt>{hiringLabels[key] ?? key}</dt><dd>{Array.isArray(value) ? value.join("; ") : value && typeof value === "object" ? `${value.id} · revision ${value.revision}` : String(value ?? "None")}</dd></div>)}</dl></article>)}</details>}
      </Card></div>
    </>}
  </div>;
}
export default function Hiring() {
  const {activeWorkspace, activeWorkspaceId, status} = useWorkspace();
  return <section><h1>HR Hiring</h1>{status !== "ready" ? <p>Loading workspace…</p> : activeWorkspace?.kind !== "organization" ?
    <p>Select an organization workspace to manage hiring. Personal workspaces do not contain organization HR records.</p> :
    <HiringWorkspace key={activeWorkspaceId} workspaceId={activeWorkspaceId}/>}</section>;
}
