import {useEffect, useState, useRef, useCallback} from "react";
import {useWorkspace} from "../hooks/useWorkspace";
import {apiClient} from "../services/apiClient";
import Button from "../components/common/Button";
import Card from "../components/common/Card";
import {hiringKinds, hiringLabels, hiringForm, hiringPayload, hiringStatuses, listFields, hiringExamples} from "../utils/hiring";
import "./Hiring.css";
import HRWorkflow from "../components/hiring/HRWorkflow";
import HRJourney from "../components/hiring/HRJourney";
import {useSimulation} from "../context/SimulationContext";
import {loadHiringWorkspace} from "../utils/hrWorkflow";
import HRReviews from "../components/hiring/HRReviews";
import HRAssistance from "../components/hiring/HRAssistance";

function HiringWorkspace({workspaceId}) {
  const [section, setSection] = useState("workflow");
  const [focus, setFocus] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [evidenceReload, setEvidenceReload] = useState(0);
  const detailRequest = useRef(0);
  const [kind, setKind] = useState("requirements");
  const [records, setRecords] = useState({});
  const [capabilities, setCapabilities] = useState(null);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(null);
  const [linkedDrafts, setLinkedDrafts] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [opening, setOpening] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveNotice,setSaveNotice]=useState("");
  const saveLock=useRef(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const invalidateDetails = () => {detailRequest.current++;};
    invalidateDetails(); setOpening(false);
    let alive = true;
    const controller = new AbortController();
    if (!evidenceReload) {setLoading(true); setForm(null); setSelected(null); setHistory([]); setRecords({}); setCapabilities(null); setSnapshot(null);}
    setError(""); setRefreshing(true);
    (async () => {
      const data = await loadHiringWorkspace(apiClient, workspaceId, controller.signal);
      if (!alive) return;
      setCapabilities(data.capabilities); setRecords(data.records); setSnapshot(data);
    })().catch(e => {if (alive) {setError(e.message); setSnapshot(null); setRecords({}); setCapabilities(null);}}).finally(() => {if (alive) {setLoading(false); setRefreshing(false);}});
    return () => {invalidateDetails(); alive = false; controller.abort();};
  }, [workspaceId, reload, evidenceReload]);
  const refreshEvidence = useCallback(() => setEvidenceReload(v => v + 1), []);
  useEffect(() => {
    if (!selected || kind === "job-descriptions" || !snapshot?.capabilities.view) {setLinkedDrafts(null); return;}
    let alive = true;
    const controller = new AbortController();
    setLinkedDrafts(null);
    apiClient.getLinkedJobDescriptions(kind, selected.id, selected.revision, workspaceId, controller.signal)
      .then(rows => {if (alive) setLinkedDrafts(rows);})
      .catch(e => {if (alive) {setError(e.message); if ([401,403,404].includes(e.status)) refreshEvidence();}});
    return () => {alive = false; controller.abort();};
  }, [kind, selected, workspaceId, snapshot, refreshEvidence]);
  const definition = hiringKinds.find(item => item.key === kind);
  const headRevision = Math.max(records[kind]?.find(item => item.id === selected?.id)?.revision ?? 0, ...history.map(item => item.revision));
  const canEdit = capabilities?.[kind.replaceAll("-", "_")] && selected?.content.status !== "archived" && !refreshing && (!selected || selected.revision >= headRevision);
  const switchKind = value => {setOpening(false);detailRequest.current++; setKind(value); setSelected(null); setForm(null); setHistory([]); setLinkedDrafts(null); setError("");};
  const openRecord = async (record, targetKind = kind, revision = record?.revision) => {
    if (!record) {setError("Record is unavailable. Reload the workspace."); return;}
    setSection("records"); setKind(targetKind);
    const requestId = ++detailRequest.current;
    setOpening(true); setSelected(null); setForm(null); setHistory([]); setLinkedDrafts(null); setError("");
    try {
      const revisions = await apiClient.getHiringRevisions(targetKind, record.id, workspaceId);
      if (requestId === detailRequest.current) {
        const exact = revisions.find(item => item.revision === revision);
        if (!exact) throw new Error("Source revision is unavailable.");
        setSelected(exact); setForm(hiringForm(targetKind, exact.content)); setHistory(revisions);
      }
    } catch (e) {if (requestId === detailRequest.current) {setError(e.message); if ([401,403,404].includes(e.status)) refreshEvidence();}}
    finally {if (requestId === detailRequest.current) setOpening(false);}
  };
  const save = async event => {
    event.preventDefault(); if(saveLock.current)return;saveLock.current=true;setSaving(true);setError("");setSaveNotice("");
    const requestId = ++detailRequest.current;
    try {
      const payload = hiringPayload(kind, form, selected?.revision);
      const saved = await apiClient.saveHiringRecord(kind, selected?.id, payload, workspaceId);
      if (requestId !== detailRequest.current) return;
      setRecords(previous => ({...previous,[kind]:[saved,...(previous[kind] ?? []).filter(item => item.id !== saved.id)]}));
      setSnapshot(previous => previous ? {...previous,records:{...previous.records,[kind]:[saved,...(previous.records[kind] ?? []).filter(item => item.id !== saved.id)]}} : previous);
      setSelected(saved); setForm(hiringForm(kind, saved.content)); setHistory([]);
      setEvidenceReload(value => value + 1);
      setSaveNotice(`${saved.content.title} saved. It is available in the hiring guide and saved records; review has not been submitted automatically.`);
    } catch (e) {setError(e.message); if ([401,403,404].includes(e.status)) refreshEvidence();}
    finally {saveLock.current=false;setSaving(false);}
  };
  const navigate = target => {
    if (saving) return;
    if (target.section === "create-record") {
      detailRequest.current++;setOpening(false);setSection("records");setKind(target.kind);setSelected(null);setHistory([]);setLinkedDrafts(null);setError("");setSaveNotice("");setForm(hiringForm(target.kind));
    } else if (target.section === "record") {
      const targetKind = target.kind ?? "job-descriptions";
      openRecord(records[targetKind]?.find(item => item.id === target.id), targetKind, target.revision);
    } else if (target.section === "create-draft") {
      detailRequest.current++; setOpening(false); setSection("records"); setKind("job-descriptions"); setSelected(null); setHistory([]);
      setForm({...hiringForm("job-descriptions"), requirement:`${target.id}@${target.revision}`});
    } else {setSection(target.section); setFocus({...target, token:Date.now()});}
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
    <p>Start with the hiring guide. Your drafts, source knowledge and human decisions are saved in this organization.</p>
    {saveNotice&&<p className="step-saved" role="status">{saveNotice}</p>}
    {loading && <p role="status">Loading hiring records…</p>}
    {error && <p role="alert" className="run-error">{error} <Button type="button" disabled={saving} onClick={() => {setEvidenceReload(0); setReload(v => v + 1);}}>Reload</Button></p>}
    {!loading && capabilities && !capabilities.view && <p role="status">An active HR Recruiter, Reviewer or Approver role is required. Manage assignments in Organizations.</p>}
    {!loading && capabilities?.view && <>
      <Button disabled={refreshing || saving} onClick={refreshEvidence}>Refresh hiring workspace</Button>
      {refreshing && <p role="status">Refreshing saved workflow…</p>}
      <nav aria-label="HR workflow navigation" className="hiring-tabs">{[["workflow", "Hiring guide"], ["records", "Saved records and drafts"], ["assistance", "AI assistance"], ["reviews", "Human review and approval"]].map(([key,label]) =>
        <Button key={key} aria-pressed={section === key} disabled={saving} onClick={() => setSection(key)}>{label}</Button>)}</nav>
      {snapshot && <div hidden={section !== "workflow"}><HRJourney snapshot={snapshot} onNavigate={navigate}/><details><summary>Saved document relationships and full workflow history</summary><HRWorkflow snapshot={snapshot} onNavigate={navigate}/></details></div>}
      <div hidden={section !== "assistance"}><HRAssistance workspaceId={workspaceId} records={records} snapshot={snapshot} onNavigate={navigate} focus={focus?.section === "assistance" ? focus : null} onChanged={refreshEvidence}/></div>
      <div hidden={section !== "reviews"}><HRReviews workspaceId={workspaceId} records={records} snapshot={snapshot} focus={focus?.section === "reviews" ? focus : null} onChanged={refreshEvidence} onRevise={id => openRecord(records["job-descriptions"]?.find(item => item.id === id), "job-descriptions")}/></div>
      <div hidden={section !== "records"}>
      <nav aria-label="Hiring sections" className="hiring-tabs">{hiringKinds.map(item => <Button type="button" key={item.key}
        aria-pressed={item.key === kind} disabled={saving} onClick={() => switchKind(item.key)}>{item.label}</Button>)}</nav>
      <div className="hiring-columns"><Card title={definition.label}>
        <Button type="button" disabled={!capabilities[kind.replaceAll("-", "_")] || saving} onClick={() => {detailRequest.current++; setOpening(false); setSelected(null); setForm(hiringForm(kind)); setHistory([]); setLinkedDrafts(null); setError("");}}>Create {kind === "job-descriptions" ? "draft" : "record"}</Button>
        {!capabilities[kind.replaceAll("-", "_")] && <p className="muted">Read-only access. HR Recruiter permission is required to edit.</p>}
        {!records[kind]?.length && <p>No records yet.</p>}
        <ul className="hiring-records">{records[kind]?.map(record => <li key={record.id}><Button type="button" disabled={saving} onClick={() => openRecord(record)}>
          {record.content.title}<small>{record.content.status} · revision {record.revision}</small></Button></li>)}</ul>
      </Card><Card title={selected ? "Record details" : "New record"}>
        {!form && <p role="status">{opening ? "Loading selected revision…" : "Select a record or create one."}</p>}
        {selected && <details><summary>Linked sources, AI runs and decision history</summary><HRWorkflow snapshot={snapshot} record={selected} kind={kind} linkedDrafts={linkedDrafts} onNavigate={navigate}/></details>}
        {selected && selected.revision < headRevision && selected.content.status !== "archived" && <p role="status">Historical revision · read-only. Select the current record to edit.</p>}
        {selected?.content.status === "archived" && <p className="muted">Archived record · read-only. Its revision history remains available.</p>}
        {form && <form onSubmit={save} className="hiring-form">
          {selected && <details><summary>Saved version and author details</summary><p className="muted">Revision {selected.revision} · {selected.id}<br/>Created by {selected.createdByUserId} · {new Date(selected.createdAt).toLocaleString()}<br/>Updated by {selected.updatedByUserId} · {new Date(selected.updatedAt).toLocaleString()}</p></details>}
          {definition.fields.filter(field=>["title","purpose","summary"].includes(field)).map(field => <label key={field}>{hiringLabels[field]}{listFields.has(field) && <small>One item per line</small>}
            {field === "openings" ? <input type="number" min="1" max="10000" step="1" required placeholder={field === "title" ? "Example: Software Engineer" : field === "purpose" ? "Explain why this role is needed and what the person will do." : "Describe the role using the saved hiring requirement."} value={form[field]} disabled={!canEdit || saving} onChange={e => setForm({...form, [field]: e.target.value})}/> :
              <textarea rows={listFields.has(field) || ["purpose", "summary"].includes(field) ? 3 : 1}
                required={["title", "purpose", "summary"].includes(field)} maxLength={["title", "department", "location", "employmentArrangement"].includes(field) ? 200 : field === "summary" ? 8000 : listFields.has(field) ? undefined : 4000}
                placeholder={hiringExamples[field]} value={form[field]} disabled={!canEdit || saving} onChange={e => setForm({...form, [field]: e.target.value})}/>}
          </label>)}
          <details className="hiring-optional"><summary>Responsibilities, skills and additional details</summary>
          {definition.fields.filter(field=>!["title","purpose","summary"].includes(field)).map(field => <label key={field}>{hiringLabels[field]}{listFields.has(field) && <small>One item per line</small>}
            {field === "openings" ? <input type="number" min="1" max="10000" step="1" required value={form[field]} disabled={!canEdit || saving} onChange={e => setForm({...form, [field]: e.target.value})}/> :
              <textarea rows={listFields.has(field) || ["purpose", "summary"].includes(field) ? 3 : 1}
                required={["title", "purpose", "summary"].includes(field)} maxLength={["title", "department", "location", "employmentArrangement"].includes(field) ? 200 : field === "summary" ? 8000 : listFields.has(field) ? undefined : 4000}
                placeholder={hiringExamples[field]} value={form[field]} disabled={!canEdit || saving} onChange={e => setForm({...form, [field]: e.target.value})}/>}
          </label>)}
          </details>
          {kind === "job-descriptions" && <>{sourceSelect("requirement", "requirements", "Source hiring requirement", true)}{sourceSelect("roleKnowledge", "role-knowledge", "Source role knowledge", false)}<p className="muted">Sources retain their selected revisions when the source records change.</p></>}
          <details><summary>Archive and lifecycle options</summary><label>Lifecycle status<select value={form.status} disabled={!canEdit || saving || !selected} onChange={e => setForm({...form, status: e.target.value})}>
            {hiringStatuses(kind, selected?.content.status).map(value => <option key={value}>{value}</option>)}
          </select></label><p>Archiving preserves saved versions and makes the record read-only. It does not approve a description.</p></details>
          <Button variant="primary" type="submit" disabled={!canEdit || saving}>{saving ? "Saving…" : kind === "job-descriptions" ? "Save job description" : kind === "requirements" ? "Save requirement" : "Save role knowledge"}</Button>
        </form>}
        {!!history.length && <details><summary>Revision history ({history.length})</summary>{history.map(record => <article key={record.revision}><h3>Revision {record.revision} · {record.content.status}</h3><Button disabled={saving} onClick={() => openRecord(record, kind, record.revision)}>Inspect revision {record.revision}</Button><p>{record.updatedByUserId} · {new Date(record.updatedAt).toLocaleString()}</p><dl>{Object.entries(record.content).map(([key, value]) => <div key={key}><dt>{hiringLabels[key] ?? key}</dt><dd>{Array.isArray(value) ? value.join("; ") : value && typeof value === "object" ? `${value.id} · revision ${value.revision}` : String(value ?? "None")}</dd></div>)}</dl></article>)}</details>}
      </Card></div></div>
    </>}
  </div>;
}
export default function Hiring() {
  const {activeWorkspace, activeWorkspaceId, status} = useWorkspace();
  const {setActivePage}=useSimulation();
  return <section><h1>HR Hiring</h1><p>Prepare a job description with optional AI help, then record authorized human review and approval.</p>{status !== "ready" ? <p>Loading workspace…</p> : activeWorkspace?.kind !== "organization" ?
    <div><p>HR Hiring needs a shared organization and an assigned Recruiter, Reviewer or Approver responsibility. Your Personal Workspace stays separate.</p><Button variant="primary" onClick={()=>setActivePage("organizations")}>Create or join an organization</Button></div> :
    <HiringWorkspace key={activeWorkspaceId} workspaceId={activeWorkspaceId}/>}</section>;
}
