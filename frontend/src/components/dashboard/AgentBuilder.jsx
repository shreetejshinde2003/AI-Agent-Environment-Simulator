import {useEffect, useRef, useState} from "react";
import Modal from "../common/Modal";
import {apiClient} from "../../services/apiClient";
import {canManageAgents, emptyAgentConfig, validateAgentConfig, validateAgentInput} from "../../utils/agentBuilder";
import "../common/Button.css";
import "./AgentBuilder.css";

export default function AgentBuilder({workspaceId, workspace, onRunCreated}) {
  const [archiving, setArchiving] = useState(false);
  const [agents, setAgents] = useState([]);
  const [options, setOptions] = useState(null);
  const [selected, setSelected] = useState(null);
  const [draft, setDraft] = useState({...emptyAgentConfig});
  const [revisions, setRevisions] = useState([]);
  const [runs, setRuns] = useState([]);
  const [run, setRun] = useState(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const mounted = useRef(false);
  const operationLock=useRef(false);
  const [eligibility,setEligibility]=useState(null),[eligibilityError,setEligibilityError]=useState("");
  const manage = canManageAgents(workspace);

  const selectedId=selected?.id,selectedVersion=selected?.revision;
  const selectedRunId=run?.id,selectedRunStatus=run?.status;
  useEffect(()=>{
    setEligibility(null);setEligibilityError("");if(!selectedId||!manage)return;
    const controller=new AbortController();
    apiClient.getAgentDeletionEligibility(selectedId,workspaceId,controller.signal).then(value=>{if(!controller.signal.aborted)setEligibility(value);}).catch(()=>{if(!controller.signal.aborted)setEligibilityError("Removal checks could not load. Reload this agent before changing its availability.");});
    return()=>controller.abort();
  },[selectedId,selectedVersion,workspaceId,manage,selectedRunId,selectedRunStatus]);
  async function reload() {
    setLoading(true); setError("");
    try {
      const [definitions, settings, savedRuns] = await Promise.all([
        apiClient.getCustomAgents(workspaceId), apiClient.getAgentBuilderOptions(workspaceId), apiClient.getTasks(workspaceId),
      ]);
      if (!mounted.current) return;
      setAgents(definitions); setOptions(settings);
      setRuns(savedRuns.filter(item => item.executionMode === "custom"));
      setRun(current => savedRuns.find(item => item.id === current?.id) ?? null);
      const refreshed = definitions.find(agent => agent.id === selected?.id) ?? null;
      setSelected(refreshed); setDraft(refreshed ? {...refreshed.config} : {...emptyAgentConfig});
    } catch (failure) {if (mounted.current) setError(failure.message);}
    finally {if (mounted.current) setLoading(false);}
  }
  useEffect(() => {
    mounted.current = true;
    if (workspaceId) reload();
    return () => {mounted.current = false;};
    // Workspace changes mount a fresh builder and isolate drafts/output.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  useEffect(() => {
    if (!run || !["queued", "in_progress"].includes(run.status)) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const result = await apiClient.getTask(run.id, workspaceId);
        if (!cancelled) setRun(result);
      } catch (failure) {
        if (!cancelled) setError(`Cannot refresh execution: ${failure.message}. Use Refresh status to retry.`);
      }
    }, 1000);
    return () => {cancelled = true; clearTimeout(timer);};
  }, [run, workspaceId]);

  function choose(agent) {
    setSelected(agent); setDraft({...agent.config}); setError(""); setNotice(""); setRevisions([]);
    setRun([...runs].reverse().find(item => item.assignedAgentId === agent.id) ?? null); setInput("");
  }
  function newAgent() {
    setSelected(null); setDraft({...emptyAgentConfig}); setRun(null); setRevisions([]); setError(""); setNotice(""); setInput("");
  }
  function field(name, value) {setDraft(current => ({...current, [name]: value})); setNotice("");}
  async function save(event) {
    event.preventDefault();if(operationLock.current)return;
    const invalid = validateAgentConfig(draft);
    if (invalid) {setError(invalid); return;}
    operationLock.current=true;setBusy(true);setError("");setNotice("");
    try {
      const saved = await apiClient.saveCustomAgent(selected?.id, selected ? {...draft, expectedRevision: selected.revision} : draft, workspaceId);
      if (!mounted.current) return;
      setSelected(saved); setDraft({...saved.config}); setRevisions([]);
      setAgents(current => [...current.filter(agent => agent.id !== saved.id), saved]); setNotice(`Saved revision ${saved.revision}.`);
    } catch (failure) {if (mounted.current) setError(failure.message);}
    finally {operationLock.current=false;if(mounted.current)setBusy(false);}
  }
  async function archive(active = false) {
    if(operationLock.current)return;operationLock.current=true;setBusy(true);setError("");
    try {
      const saved = await apiClient.saveCustomAgent(selected.id, {...selected.config, active, expectedRevision: selected.revision}, workspaceId);
      if (!mounted.current) return;
      setSelected(saved); setDraft({...saved.config}); setArchiving(false);
      setAgents(current => current.map(agent => agent.id === saved.id ? saved : agent));
      setNotice(active ? "Agent reactivated. It is available for new runs." : "Agent archived. Saved revisions and historical runs remain available.");
    } catch (failure) {if (mounted.current) setError(failure.message);}
    finally {operationLock.current=false;if(mounted.current)setBusy(false);}
  }
  async function execute(event) {
    event.preventDefault();if(operationLock.current)return;
    const invalid = validateAgentInput(input);
    if (invalid) {setError(invalid); return;}
    operationLock.current=true;setBusy(true);setError("");setNotice("");
    try {
      const queued = await apiClient.runCustomAgent(selected.id, {text: input.trim(), expectedRevision: selected.revision}, workspaceId);
      if (!mounted.current) return;
      onRunCreated?.(queued);
      setRun(queued); setRuns(current => [...current, queued]); setNotice(`Run accepted using saved revision ${queued.customAgentRevision}.`);
    } catch (failure) {
      if (mounted.current) setError(failure.outcomeUnknown ? `Run acknowledgement unavailable. Refresh runs before retrying: ${failure.message}` : failure.message);
    } finally {operationLock.current=false;if (mounted.current) setBusy(false);}
  }
  async function history() {
    if(operationLock.current)return;operationLock.current=true;
    setBusy(true);
    try {
      const saved = await apiClient.getCustomAgentRevisions(selected.id, workspaceId);
      if (mounted.current) setRevisions(saved);
    } catch (failure) {if (mounted.current) setError(failure.message);}
    finally {operationLock.current=false;if(mounted.current)setBusy(false);}
  }
  async function refreshRun() {
    if(operationLock.current)return;operationLock.current=true;
    setBusy(true);
    try {
      const saved = await apiClient.getTask(run.id, workspaceId);
      if (mounted.current) {setRun(saved); setError("");}
    } catch (failure) {if (mounted.current) setError(failure.message);}
    finally {operationLock.current=false;if(mounted.current)setBusy(false);}
  }
  const live = run && ["queued", "in_progress"].includes(run.status);
  return <section className="agent-builder" aria-label="Agent Builder">
    <div className="builder-toolbar"><div><h2>Agent Builder</h2><p className="muted">Create a saved text agent and run it in this workspace.</p></div>
      <button className="btn btn-default" onClick={reload} disabled={loading || busy}>Refresh agents and runs</button>
      {manage && <button className="btn btn-default" onClick={newAgent} disabled={busy}>New agent</button>}
    </div>
    {error && <p className="run-error" role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {loading ? <p role="status">Loading agents…</p> : <div className="builder-layout">
      <aside aria-label="Saved custom agents">
        {!agents.length && <p className="muted">No custom agents saved in this workspace.</p>}
        {agents.map(agent => <button className="builder-agent btn btn-default" key={agent.id} onClick={() => choose(agent)} disabled={busy}
          aria-pressed={selected?.id === agent.id}><strong>{agent.config.name}</strong><span>Revision {agent.revision} · {agent.config.active ? "Active" : "Archived"}</span></button>)}
      </aside>
      <div className="workspace-stack">
        {(!selected && !manage) ? <p className="muted">Select an agent to inspect or run it. Workspace owners and admins manage definitions.</p> : <>
          <form onSubmit={save} aria-label="Agent configuration">
            <h3>{selected ? selected.config.name : "New agent"}</h3>
            <fieldset disabled={!manage || busy}>
              <label>Name<input placeholder="Example: Meeting summary assistant" value={draft.name} onChange={event => field("name", event.target.value)} maxLength={80} required /></label>
              <p>Give the agent a clear purpose and instructions, then save it. Run it with input text to create a result in this workspace.</p><label>Description<textarea aria-label="Description" value={draft.description} onChange={event => field("description", event.target.value)} maxLength={1000} /></label>
              <label>Purpose<textarea aria-label="Purpose" placeholder="Example: Summarize decisions and action owners" value={draft.purpose} onChange={event => field("purpose", event.target.value)} maxLength={1000} required /></label>
              <label>Instructions<textarea aria-label="Instructions" placeholder="Describe what the answer should include and how it should be formatted" className="builder-instructions" value={draft.instructions} onChange={event => field("instructions", event.target.value)} maxLength={8000} required /></label>
              <details><summary>Model and execution limits</summary><div className="builder-fields">
                <label>Model<select value={draft.model} onChange={event => field("model", event.target.value)}>
                  <option value="default">Default · {options?.models.default}</option><option value="fast">Fast · {options?.models.fast}</option></select></label>
                <label>Output token limit<input type="number" min={64} max={1024} required value={draft.maxTokens} onChange={event => field("maxTokens", Number(event.target.value))} /></label>
                <label>Timeout (seconds)<input type="number" min={1} max={120} required value={draft.timeoutSeconds} onChange={event => field("timeoutSeconds", Number(event.target.value))} /></label>
              </div>
              </details><label className="builder-checkbox"><input type="checkbox" checked={draft.active} onChange={event => field("active", event.target.checked)} />Active (turn off to archive)</label>
              {manage && <button className="btn btn-primary" type="submit">{busy ? "Working…" : "Save agent"}</button>}
            </fieldset>
            <p className="muted">Groq · Text input → Text output. Agents generate text using the configured model. Instructions do not grant tools or workspace access.</p>
          </form>
          {selected && <>
            <details><summary>Saved version and technical details</summary><dl className="metadata"><dt>Agent ID</dt><dd>{selected.id}</dd><dt>Saved revision / model</dt><dd>{selected.revision} / {selected.resolvedModel}</dd>
              <dt>Configuration fingerprint</dt><dd className="builder-hash">{selected.configHash}</dd></dl></details>
            {manage && !selected.config.active && <button className="btn btn-primary" onClick={()=>archive(true)} disabled={busy}>Reactivate custom agent</button>}
            {manage && <details><summary>Archive or permanent removal</summary><p>Archive stops future selection while keeping saved work. Permanent deletion would remove the definition and requires server-verified eligibility.</p>{eligibilityError&&<p role="alert">{eligibilityError}</p>}{!eligibility&&!eligibilityError&&<p role="status">Checking saved dependencies…</p>}{eligibility&&<p>{eligibility.message} {eligibility.revisionCount} saved version(s) and {eligibility.runCount} retained run(s).</p>}<button className="btn btn-default" disabled aria-describedby="agent-removal-reason">Delete permanently</button><p id="agent-removal-reason">Permanent deletion is unavailable under the current immutable-version policy, including unused saved agents. Archive is available instead.</p></details>}
            {manage && selected.config.active && <button className="btn btn-default" onClick={() => setArchiving(true)} disabled={busy}>Archive custom agent</button>}
            {archiving && <Modal title="Archive custom agent" onClose={() => setArchiving(false)} canDismiss={!busy}><p>This agent will be unavailable for new runs. Historical runs and revisions remain available.</p>{error && <p role="alert">{error}</p>}<button disabled={busy} onClick={()=>archive(false)}>Confirm archive</button></Modal>}
            <button className="btn btn-default" onClick={history} disabled={busy}>Inspect revision history</button>
            {revisions.map(version => <details key={version.revision}><summary>Revision {version.revision} · {new Date(version.updatedAt).toLocaleString()} · {version.config.active ? "Active" : "Archived"}</summary>
              <p>Saved by {version.updatedByUserId} · {version.resolvedModel}</p><pre>{JSON.stringify(version.config, null, 2)}</pre></details>)}
            <form onSubmit={execute} aria-label="Run saved agent"><h3>Run saved agent</h3><p className="muted">Uses the saved version. Save edits first. This invokes the configured AI provider; it does not grant tools or approval authority. Results are saved with this agent and in Simulation History.</p>
              <label>Input text<textarea aria-label="Input text" value={input} onChange={event => setInput(event.target.value)} maxLength={10000} required disabled={busy || live || !selected.config.active} /></label>
              <button className="btn btn-primary" type="submit" disabled={busy || live || !selected.config.active}>Run agent</button>
              {!selected.config.active && <p className="muted">This agent is inactive. A manager must activate it before execution.</p>}
            </form>
            {runs.some(item => item.assignedAgentId === selected.id) && <label>Saved runs<select disabled={busy} value={run?.id ?? ""} onChange={event => setRun(runs.find(item => item.id === event.target.value))}>
              <option value="" disabled>Select a run</option>{runs.filter(item => item.assignedAgentId === selected.id).map(item => <option key={item.id} value={item.id}>{item.id} · revision {item.customAgentRevision}</option>)}</select></label>}
            {run && <section aria-label="Agent execution result"><h3>Execution result</h3><p role="status">{run.status} · Revision {run.customAgentRevision}</p>
              <p className="muted">{run.id}</p><button className="btn btn-default" onClick={refreshRun} disabled={busy}>Refresh status</button>
              {run.error && <p className="run-error" role="alert">{run.error}</p>}{run.output && <pre>{run.output}</pre>}
              {run.stages?.[0]?.startedAt && <p className="muted">Model: {run.stages[0].model ?? "Not recorded"} · Tokens: {run.stages[0].totalTokens ?? "Not recorded"} · Stage time: {run.stages[0].durationSeconds?.toFixed(2) ?? "Pending"}s</p>}
            </section>}
          </>}
        </>}
      </div>
    </div>}
  </section>;
}
