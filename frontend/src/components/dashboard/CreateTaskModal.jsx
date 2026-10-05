import { useEffect, useRef, useState } from "react";
import Modal from "../common/Modal";
import Button from "../common/Button";
import { apiClient } from "../../services/apiClient";
import { useSimulation } from "../../context/SimulationContext";
import { useWorkspace } from "../../hooks/useWorkspace";
import { datasetOptions, DATASET_EMPTY } from "../../utils/runs";
import {ADAPTIVE_CATEGORIES, createRequestLock, EXECUTION_STRATEGIES, runRequest, specialistAgents, validateReferenceFiles, validateRunDraft} from "../../utils/runComposer";
import "./AgentActionForms.css";
import "./CreateTaskModal.css";

export function RunConfigurationForm({draft, onChange, agents, datasets, datasetError, uploads, work, error, onSubmit, onUpload, onDetach, onClose}) {
  const options = datasetOptions(datasets);
  const selectedDataset = datasets?.find(dataset => dataset.datasetId === draft.datasetId);
  const busy = !!work;
  return <form className="run-composer" onSubmit={onSubmit} aria-busy={busy}>
    <p className="muted">Configure one simulation run. Results and recorded execution remain available in History.</p>
    {error && <div className="form-error" role="alert" tabIndex={-1} data-composer-error>
      {error.message}{error.outcomeUnknown && <p>The submission outcome is not confirmed. Check Simulation History before submitting again.</p>}
    </div>}
    {busy && <p role="status" tabIndex={-1} data-composer-busy>{work === "uploading" ? "Uploading reference data…" : "Submitting run…"} Keep this dialog open until the request finishes.</p>}
    <fieldset className="composer-fields" disabled={busy}>
      <legend className="sr-only">Run configuration</legend>
      <section aria-labelledby="composer-goal-heading"><h4 id="composer-goal-heading">Goal</h4>
        <div className="form-field"><label htmlFor="task-directive">Goal / directive</label>
          <textarea id="task-directive" required maxLength={10000} value={draft.directive} autoFocus
            onChange={event => onChange({directive: event.target.value})} placeholder="What should this run accomplish?"/></div>
        <div className="form-field"><label htmlFor="task-title">Run title · optional</label>
          <input id="task-title" maxLength={120} value={draft.title} onChange={event => onChange({title: event.target.value})}
            placeholder="A short label to find this run later" aria-describedby="composer-title-help"/>
          <p className="muted" id="composer-title-help">Leave blank to use a compact title from the goal. Stored titles use up to 80 characters; the immutable run ID is retained separately.</p></div>
      </section>
      <fieldset className="composer-strategies"><legend>Execution strategy</legend>
        <div className="strategy-options">{EXECUTION_STRATEGIES.map(strategy => <label className="strategy-option" key={strategy.value}>
          <input type="radio" name="executionMode" value={strategy.value} checked={draft.executionMode === strategy.value}
            aria-label={`${strategy.label} · ${strategy.subtitle}`} aria-describedby={`strategy-${strategy.value}-help`}
            onChange={() => onChange({executionMode: strategy.value, taskType: ""})}/>
          <span><strong>{strategy.label}</strong><span>{strategy.subtitle}</span><small id={`strategy-${strategy.value}-help`}>{strategy.description}</small></span>
        </label>)}</div>
        <details className="composer-utility"><summary>Individual Specialist · legacy utility</summary>
          <label className="strategy-option"><input type="radio" name="executionMode" value="single_agent"
            checked={draft.executionMode === "single_agent"} aria-label="Individual Specialist · legacy utility"
            onChange={() => onChange({executionMode: "single_agent", taskType: ""})}/>
            <span><strong>Individual Specialist</strong><small>Utility/debug execution of one specialist. Separate from the Single, Fixed and Adaptive research baselines.</small></span></label>
          {draft.executionMode === "single_agent" && <div className="form-field"><label htmlFor="task-agent">Specialist</label>
            <select id="task-agent" value={draft.assignedAgentId} onChange={event => onChange({assignedAgentId: event.target.value})}>
              {specialistAgents(agents).map(agent => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
            </select><p className="muted">Some specialists require source material. Reference uploads are not sent by this legacy utility; existing draft attachments are retained when you return to a research mode.</p></div>}
        </details>
      </fieldset>
      <section aria-labelledby="composer-context-heading"><h4 id="composer-context-heading">Context · optional</h4>
        <div className="form-field"><label htmlFor="benchmark-dataset">Benchmark dataset</label>
          <select id="benchmark-dataset" value={draft.datasetId} onChange={event => onChange({datasetId: event.target.value})}
            disabled={datasets === null || datasetError || !options.length} aria-describedby="composer-dataset-help">
            <option value="">None · no benchmark context</option>{options.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}
          </select>
          <p className="muted" id="composer-dataset-help">{datasetError ? "Benchmark registry unavailable. You can run without a benchmark." : datasets === null ? "Loading registered datasets…" : !datasets.length ? DATASET_EMPTY : !options.length ? "No active benchmark datasets on this server. No benchmark context will be attached." : draft.datasetId ?
            `Selected: ${options.find(option => option.id === draft.datasetId)?.label ?? "Unavailable dataset"}. Registered and active; the server validates its private file when the run is created.` : "No benchmark selected. Only registered active datasets are listed."}</p>
          {selectedDataset?.active && <p className="muted">Only bounded, non-personal aggregates reach agents; raw benchmark records stay on the server.</p>}
        </div>
        {draft.executionMode !== "single_agent" && <>
          <div className="form-field"><label htmlFor="context-files">Reference data · TXT, CSV, JSON</label>
            <input id="context-files" type="file" accept=".txt,.csv,.json" multiple disabled={uploads.length >= 3} onChange={onUpload}
              aria-describedby="composer-upload-help"/>
            <p className="muted" id="composer-upload-help">Up to 3 files, 256 KiB each. Prepared context uses up to 6,000 characters/file and 20 CSV rows.
              Uploads are not automatically anonymized. This shared workspace must not receive confidential data or credentials.</p></div>
          {uploads.map(upload => <div key={upload.id} className="upload-preview">
            <details><summary>{upload.filename} · {upload.sizeBytes} bytes{upload.truncated ? " · Context truncated" : ""}</summary>
              {upload.rowCount != null && <p>{upload.rowCount} rows · {upload.columns?.join(", ")}</p>}
              <pre tabIndex={0} aria-label={`Prepared preview for ${upload.filename}`}>{upload.preview}</pre></details>
            <button type="button" aria-label={`Detach ${upload.filename}`} onClick={() => onDetach(upload.id)}>Detach</button>
            <p className="muted">Detach removes this draft's reference; it does not delete the stored upload.</p>
          </div>)}
        </>}
      </section>
      {draft.executionMode === "adaptive" ? <div className="form-field"><label htmlFor="task-type">Adaptive task category</label>
        <select id="task-type" value={draft.taskType} onChange={event => onChange({taskType: event.target.value})}>
          <option value="">Infer from goal and supplied context</option>{ADAPTIVE_CATEGORIES.map(type => <option key={type} value={type}>{type.replaceAll("_", " ")}</option>)}
        </select><p className="muted">An explicit category overrides keyword inference. Summarization needs an attachment, benchmark, or a new line beginning “Source:” followed by the material.</p></div> :
        draft.datasetId && <div className="form-field"><label htmlFor="task-type">Task type · optional</label>
          <input id="task-type" maxLength={80} value={draft.taskType} onChange={event => onChange({taskType: event.target.value})}/></div>}
    </fieldset>
    <div className="form-actions"><Button type="button" variant="ghost" disabled={busy} onClick={onClose}>Cancel</Button>
      <Button type="submit" variant="primary" disabled={busy || !draft.directive.trim()}>{work === "uploading" ? "Uploading…" : busy ? "Submitting…" : "Run simulation"}</Button></div>
  </form>;
}

export default function CreateTaskModal({agents, onClose}) {
  const {openCreatedRun} = useSimulation();
  const {activeWorkspaceId, activeWorkspace} = useWorkspace();
  const [draft, setDraft] = useState({directive: "", title: "", executionMode: "fixed", assignedAgentId: "research", datasetId: "", taskType: ""});
  const [uploads, setUploads] = useState([]);
  const [datasets, setDatasets] = useState(null);
  const [datasetError, setDatasetError] = useState(false);
  const [work, setWork] = useState(null);
  const [error, setError] = useState(null);
  const lock = useRef(createRequestLock()), returnFocus = useRef(null);
  const previousWork = useRef(null);
  useEffect(() => {
    if (error) document.querySelector("[data-composer-error]")?.focus();
    else if (work) document.querySelector("[data-composer-busy]")?.focus();
    else if (previousWork.current === "uploading") (document.querySelector("#context-files:not(:disabled)") || document.querySelector(".upload-preview button"))?.focus();
    previousWork.current = work;
  }, [error, work]);
  useEffect(() => {
    let active = true;
    apiClient.getDatasets().then(items => { if (active) setDatasets(items); })
      .catch(() => { if (active) setDatasetError(true); });
    return () => { active = false; };
  }, []);
  async function uploadFiles(event) {
    const files = [...event.target.files]; event.target.value = "";
    if (!files.length) return;
    const invalid = validateReferenceFiles(files, uploads.length);
    if (invalid) { setError(new Error(invalid)); return; }
    if (!lock.current.acquire()) return;
    setWork("uploading"); setError(null);
    try {
      if (!activeWorkspaceId) throw new Error("Workspace is still resolving. Try again.");
      for (const file of files) {
        const uploaded = await apiClient.upload(file, activeWorkspaceId);
        setUploads(previous => [...previous, uploaded]);
      }
    } catch (err) { setError(err); }
    finally { lock.current.release(); setWork(null); }
  }
  async function submit(event) {
    event.preventDefault();
    const invalid = validateRunDraft(draft, agents, datasets);
    if (invalid) { setError(new Error(invalid)); return; }
    if (!lock.current.acquire()) return;
    setWork("submitting"); setError(null);
    try {
      if (!activeWorkspaceId) throw new Error("Workspace is still resolving. Try again.");
      const run = await apiClient.createTask(runRequest(draft, uploads), activeWorkspaceId);
      returnFocus.current = "[data-run-heading]";
      openCreatedRun(run); onClose();
    } catch (err) { setError(err); }
    finally { lock.current.release(); setWork(null); }
  }
  return <Modal title="New run" className="run-composer-dialog" onClose={onClose} canDismiss={!work} returnFocusRef={returnFocus}>
    <p className="muted">Run workspace: <strong>{activeWorkspace?.name ?? "Resolving…"}</strong></p>
    <RunConfigurationForm draft={draft} onChange={patch => setDraft(previous => ({...previous, ...patch}))}
      agents={agents} datasets={datasets} datasetError={datasetError} uploads={uploads} work={work} error={error}
      onSubmit={submit} onUpload={uploadFiles} onDetach={id => setUploads(previous => previous.filter(upload => upload.id !== id))} onClose={onClose}/>
  </Modal>;
}
