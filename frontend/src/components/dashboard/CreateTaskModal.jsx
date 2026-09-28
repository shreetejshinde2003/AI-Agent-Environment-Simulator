import { useState } from "react";
import Modal from "../common/Modal";
import Button from "../common/Button";
import { apiClient } from "../../services/apiClient";
import { useSimulation } from "../../context/SimulationContext";
import "./AgentActionForms.css";
export default function CreateTaskModal({agents, onClose}) {
  const {selectTask, refresh} = useSimulation();
  const [directive, setDirective] = useState("");
  const [executionMode, setExecutionMode] = useState("full_pipeline");
  const [assignedAgentId, setAgent] = useState("research");
  const [uploads, setUploads] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
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
        assignedAgentId: executionMode === "full_pipeline" ? "orchestrator" : assignedAgentId,
        uploadIds: executionMode === "full_pipeline" ? uploads.map(u => u.id) : []});
      await refresh(); selectTask(run.id); onClose();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <Modal title="Create Simulation" onClose={busy ? () => {} : onClose}>
    <form onSubmit={submit}>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="form-field"><label htmlFor="task-directive">Goal / directive</label>
        <textarea id="task-directive" required maxLength={10000} value={directive}
          onChange={e => setDirective(e.target.value)} autoFocus
          placeholder="What should the agents accomplish?"/></div>
      <div className="form-field"><label htmlFor="task-execution-mode">Execution mode</label>
        <select id="task-execution-mode" value={executionMode} onChange={e => setExecutionMode(e.target.value)}>
          <option value="full_pipeline">Full Multi-Agent Pipeline</option>
          <option value="single_agent">Individual Agent</option>
        </select></div>
      {executionMode === "single_agent" ? <div className="form-field">
        <label htmlFor="task-agent">Agent</label><select id="task-agent" value={assignedAgentId} onChange={e => setAgent(e.target.value)}>
          {agents.filter(a => a.implemented).map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select><p className="muted">Web Search is not implemented. Orchestrator is a coordinator, not an executable agent.</p>
      </div> : <>
        <p className="muted">Research → Data → Analysis → Summarizer → Report</p>
        <div className="form-field"><label htmlFor="context-files">Optional reference data · TXT, CSV, JSON</label>
          <input id="context-files" type="file" accept=".txt,.csv,.json" multiple disabled={busy || uploads.length >= 3} onChange={uploadFiles}/>
          <p className="muted">Up to 3 files, 256 KiB each. Research and Data receive prepared context: up to 6,000 characters/file and 20 CSV rows.
            This is a shared workspace—do not upload confidential data or credentials.</p>
        </div>
        {uploads.map(u => <div key={u.id} className="upload-preview">
          <details><summary>{u.filename} · {u.sizeBytes} bytes{u.truncated ? " · Context truncated" : ""}</summary>
            {u.rowCount != null && <p>{u.rowCount} rows · {u.columns.join(", ")}</p>}<pre>{u.preview}</pre></details>
          <button type="button" disabled={busy} onClick={() => setUploads(previous => previous.filter(v => v.id !== u.id))}>Detach</button>
        </div>)}
      </>}
      <div className="form-actions"><Button type="button" variant="ghost" disabled={busy} onClick={onClose}>Cancel</Button>
        <Button type="submit" variant="primary" disabled={busy || !directive.trim()}>{busy ? "Working…" : "Start Simulation"}</Button></div>
    </form>
  </Modal>;
}
