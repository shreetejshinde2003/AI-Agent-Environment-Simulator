import { useEffect, useState } from "react";
import Modal from "../common/Modal";
import Button from "../common/Button";
import { apiClient } from "../../services/apiClient";
import { useSimulation } from "../../context/SimulationContext";
import { datasetOptions, DATASET_EMPTY } from "../../utils/runs";
import "./AgentActionForms.css";
export default function CreateTaskModal({agents, onClose}) {
  const {openCreatedRun} = useSimulation();
  const [directive, setDirective] = useState("");
  const [executionMode, setExecutionMode] = useState("fixed");
  const [assignedAgentId, setAgent] = useState("research");
  const [uploads, setUploads] = useState([]);
  const [datasets, setDatasets] = useState(null);
  const [datasetError, setDatasetError] = useState(false);
  const [datasetId, setDatasetId] = useState("");
  const [taskType, setTaskType] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    let active = true;
    apiClient.getDatasets().then(items => { if (active) setDatasets(items); })
      .catch(() => { if (active) setDatasetError(true); });
    return () => { active = false; };
  }, []);
  async function uploadFiles(event) {
    const files = [...event.target.files]; event.target.value = "";
    if (files.length + uploads.length > 3) { setError("Maximum three files per simulation."); return; }
    setBusy(true); setError(null);
    try {
      for (const file of files) {
        if (file.size > 262144) throw new Error("Each file must be 256 KiB or smaller.");
        const uploaded = await apiClient.upload(file);
        setUploads(previous => [...previous, uploaded]);
      }
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      const run = await apiClient.createTask({directive: directive.trim(), executionMode,
        assignedAgentId: ["fixed", "adaptive"].includes(executionMode) ? "orchestrator" : executionMode === "single" ? "direct" : assignedAgentId,
        uploadIds: executionMode === "single_agent" ? [] : uploads.map(u => u.id),
        datasetId: datasetId || null, taskType: taskType.trim() || null});
      openCreatedRun(run); onClose();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <Modal title="Create Simulation" onClose={onClose} canDismiss={!busy}>
    <form onSubmit={submit} aria-busy={busy}>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="form-field"><label htmlFor="task-directive">Goal / directive</label>
        <textarea id="task-directive" required maxLength={10000} value={directive}
          onChange={e => setDirective(e.target.value)} autoFocus
          placeholder="What should the agents accomplish?"/></div>
      <div className="form-field"><label htmlFor="task-execution-mode">Execution mode</label>
        <select id="task-execution-mode" value={executionMode} onChange={e => { setExecutionMode(e.target.value); setTaskType(""); }}>
          <option value="fixed">Fixed Multi-Agent Pipeline</option>
          <option value="single">Single Agent · Direct Baseline</option>
          <option value="adaptive">Adaptive Multi-Agent · Rule-based</option>
          <option value="single_agent">Individual Specialist · Legacy</option>
        </select></div>
      {executionMode === "single_agent" ? <div className="form-field">
        <label htmlFor="task-agent">Agent</label><select id="task-agent" value={assignedAgentId} onChange={e => setAgent(e.target.value)}>
          {agents.filter(a => a.implemented && a.id !== "direct").map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select><p className="muted">Web Search is not implemented. Orchestrator is a coordinator, not an executable agent.</p>
      </div> : <>
        <p className="muted">{executionMode === "fixed" ? "Research → Data → Analysis → Summarizer → Report" :
          executionMode === "adaptive" ? "Deterministic capability selection. Only selected specialists execute; no routing model call." :
          "One direct-answer model call. No specialist handoffs."}</p>
        <div className="form-field"><label htmlFor="context-files">Optional reference data · TXT, CSV, JSON</label>
          <input id="context-files" type="file" accept=".txt,.csv,.json" multiple disabled={busy || uploads.length >= 3} onChange={uploadFiles}/>
          <p className="muted">Up to 3 files, 256 KiB each. Selected agents receive prepared context: up to 6,000 characters/file and 20 CSV rows.
            This is a shared workspace—do not upload confidential data or credentials.</p>
        </div>
        {uploads.map(u => <div key={u.id} className="upload-preview">
          <details><summary>{u.filename} · {u.sizeBytes} bytes{u.truncated ? " · Context truncated" : ""}</summary>
            {u.rowCount != null && <p>{u.rowCount} rows · {u.columns.join(", ")}</p>}<pre>{u.preview}</pre></details>
          <button type="button" disabled={busy} onClick={() => setUploads(previous => previous.filter(v => v.id !== u.id))}>Detach</button>
        </div>)}
      </>}
      <div className="form-field"><p>Benchmark dataset · optional</p>
        {!!datasetOptions(datasets).length && <label htmlFor="benchmark-dataset">Registered datasets</label>}
        {!!datasetOptions(datasets).length && <select id="benchmark-dataset" value={datasetId} onChange={e => setDatasetId(e.target.value)}
          disabled={busy || !datasets?.some(item => item.active)}>
          <option value="">None</option>
          {datasetOptions(datasets).map(item =>
            <option key={item.id} value={item.id}>
              {item.label}
            </option>)}
        </select>}
        <p className="muted">{datasetError ? "Benchmark registry unavailable." : datasets === null ?
          "Loading registered datasets…" : datasets.length === 0 ?
          DATASET_EMPTY : !datasets.some(item => item.active) ?
          "No active benchmark datasets on this server." :
          "Only bounded, non-personal aggregates reach agents; raw records stay on the server."}</p>
      </div>
      {executionMode === "adaptive" ? <div className="form-field"><label htmlFor="task-type">Task category</label>
        <select id="task-type" value={taskType} onChange={e => setTaskType(e.target.value)}>
          <option value="">Infer from goal and supplied context</option>
          {["summarization", "transformation", "analysis", "reporting", "research_synthesis", "structured_data_analysis", "mixed"].map(type =>
            <option key={type} value={type}>{type.replaceAll("_", " ")}</option>)}
        </select><p className="muted">An explicit category overrides keyword inference. Summarization needs an attachment, benchmark, or a new line beginning “Source:” followed by the material.</p>
      </div> : datasetId && <div className="form-field"><label htmlFor="task-type">Task type · optional</label>
        <input id="task-type" maxLength={80} value={taskType} onChange={e => setTaskType(e.target.value)}
          placeholder="e.g. descriptive_summary"/>
      </div>}
      <div className="form-actions"><Button type="button" variant="ghost" disabled={busy} onClick={onClose}>Cancel</Button>
        <Button type="submit" variant="primary" disabled={busy || !directive.trim()}>{busy ? "Submitting…" : "Start Simulation"}</Button></div>
    </form>
  </Modal>;
}
