import {useEffect, useRef, useState} from "react";
import {useWorkspace} from "../hooks/useWorkspace";
import {useSimulation} from "../context/SimulationContext";
import {apiClient} from "../services/apiClient";
import {researchPayload, scorePayload, measured} from "../utils/research";
import "./ResearchLab.css";
import OutputViewer from "../components/dashboard/OutputViewer";
import ResearchSample from "../components/dashboard/ResearchSample";
import Modal from "../components/common/Modal";
import {modeDescriptions} from "../utils/researchSample";

const MODES = ["single", "fixed", "adaptive"];
const HUMAN_DIMENSIONS = ["correctness", "relevance", "completeness", "clarity", "groundedness", "concision", "sourceConsistency"];

export function ExportedResearchReport({report}) {
  if (!report) return null;
  return <details><summary>Evidence report ready</summary>
    <p>Download requested. The complete JSON below remains available to select and copy if this browser does not save files.</p>
    <textarea aria-label="Exported research report JSON" readOnly rows={12} value={JSON.stringify(report,null,2)}/>
  </details>;
}

export function ComparisonTable({summary}) {
  if (!summary) return <p>No comparison selected. Choose a persisted experiment.</p>;
  return <>
    <p role="status">{summary.status} · {summary.configuration.evidenceKind === "deterministic_fixture" ? "Deterministic fixture evidence — no live model conclusions" : "Provider execution evidence"}</p>
    <p>{summary.statisticalScope}</p>
    {!!summary.integrityIssues.length && <p role="alert">Comparison blocked: {summary.integrityIssues.join("; ")}</p>}
    <div className="research-table-scroll" tabIndex={0} aria-label="Mode comparison table">
      <table><caption>Per benchmark and mode · means include only measured terminal runs; n is shown</caption>
        <thead><tr><th>Benchmark / Mode</th><th>Trials</th><th>Success</th><th>Latency, seconds</th><th>Tokens</th><th>Stage starts</th><th>Handoffs</th><th>Deterministic quality</th><th>Human quality, 1–5</th></tr></thead>
        <tbody>{summary.cells.map(c => <tr key={c.benchmarkId+c.mode}>
          <th scope="row">{c.benchmarkId} / {c.mode}</th><td>{c.terminalTrials}/{c.expectedTrials}</td><td>{measured(c.successRate, true)}</td>
          {[c.latency,c.tokens,c.agentCalls,c.handoffs,c.deterministicQuality,c.humanQuality].map((v,i) => <td key={i}>{measured(v.mean, i===4)} (n={v.n})<br/><small>range {measured(v.min)}–{measured(v.max)} · SD {measured(v.sampleStdDev)}</small></td>)}
        </tr>)}</tbody></table>
    </div>
    {summary.cells.some(c=>c.mode==="adaptive") && <details><summary>Adaptive route stability and avoidance</summary>
      <ul>{summary.cells.filter(c=>c.mode==="adaptive").map(c=><li key={c.benchmarkId}>{c.benchmarkId}: route consistency {measured(c.routeConsistency,true)} · mean skipped specialists {measured(c.skippedAgentCount?.mean)}. {c.routeVariants?.map(v=>`${v.agents.join(" → ")} (${v.count} trials)`).join("; ")}</li>)}</ul>
      <p>Recorded avoidance counts describe routing. Quality evidence is needed to decide whether each avoided stage was unnecessary.</p>
    </details>}
    <details><summary>Configuration and limitations</summary><pre>{JSON.stringify(summary.configuration,null,2)}</pre><ul>{summary.limitations.map(text=><li key={text}>{text}</li>)}</ul></details>
  </>;
}

export function ResearchRun({run, task, onInspect, onReview, busy}) {
  const [scores,setScores] = useState({});
  const [notes,setNotes] = useState("");
  const [error,setError] = useState("");
  async function submit(event) {
    event.preventDefault(); setError("");
    try {await onReview(scorePayload(run,task,scores,notes)); setNotes("");}
    catch (err) {setError(err.message);}
  }
  return <section className="research-run">
    <h3>Trial {run.trialNumber} · {run.benchmarkId} · {run.mode}</h3>
    <p>{run.status}</p>{run.error && <p role="alert">{run.error}</p>}<details><summary>Trial execution and reproducibility details</summary><p>{run.taskId}</p>
    <p>Completed: {run.completedAgents.join(", ") || "None"} · Failed: {run.failedStages.join(", ") || "None"}</p>
    <p>Selected route: {run.selectedAgents?.join(" → ") ?? "Not adaptive"} · Skipped: {run.skippedAgents?.join(", ") ?? "Not adaptive"}</p>
    <p>Not executed: {run.notExecutedAgents.join(", ") || "None"} · Stage starts: {run.agentCalls} · Handoffs: {run.handoffs}</p>
    <p>Tokens: {measured(run.totalTokens.value)} · {run.totalTokens.coverage} coverage · Observed timeout: {run.timeoutObserved ? "Yes" : "No explicit evidence"}</p>
    </details><button type="button" onClick={onInspect}>Open run evidence</button>
    <details><summary>Stage timings and deterministic checks</summary><pre>{JSON.stringify({timings:run.stageTimings,quality:run.deterministicQuality},null,2)}</pre></details>
    {task ? <OutputViewer key={task.id} text={task.output} directive={task.directive} contract={task.stages?.find(s=>s.output===task.output&&s.outputContract)?.outputContract}/> : <p>Loading saved output…</p>}
    {task?.output && run.status === "completed" && <form onSubmit={submit}>
      <h4>Human rubric · human-v1</h4><p>1 materially wrong/missing · 2 major weaknesses · 3 adequate with omissions · 4 strong, minor weaknesses · 5 fully meets criterion. Groundedness concerns unsupported claims; source consistency concerns contradictions. Concision rewards useful brevity.</p>
      <div className="research-score-grid">{HUMAN_DIMENSIONS.map(d => <label key={d}>{d.replace(/([A-Z])/g," $1")}
        <select required value={scores[d] ?? ""} onChange={e=>setScores({...scores,[d]:Number(e.target.value)})} disabled={busy}><option value="">Score</option>{[1,2,3,4,5].map(n=><option key={n} value={n}>{n}</option>)}</select>
      </label>)}</div>
      <label>Review rationale<textarea required maxLength={2000} value={notes} onChange={e=>setNotes(e.target.value)} disabled={busy}/></label>
      <button disabled={busy}>Save human scores</button>{error && <p role="alert">{error}</p>}
      {run.humanReview && <p>Latest score {run.humanScore}/5 · {run.humanReview.reviewerId} · {run.humanReview.reviewedAt}. {run.humanReview.assessment.notes}</p>}
      <details><summary>Review history and original source</summary><pre>{JSON.stringify({source:task.research.benchmark.source, reviews:task.humanReviews},null,2)}</pre></details>
    </form>}
  </section>;
}

function ResearchWorkspace({workspaceId}) {
  const {selectTask,setActivePage,acceptRun} = useSimulation();
  const [view,setView]=useState("welcome"),[confirming,setConfirming]=useState(false);
  const [registry,setRegistry]=useState(null), [experiments,setExperiments]=useState([]);
  const [selected,setSelected]=useState(""),[summary,setSummary]=useState(null);
  const [cases,setCases]=useState([]),[modes,setModes]=useState(MODES),[repetitions,setRepetitions]=useState(1);
  const [purpose,setPurpose]=useState("Compare execution modes on safe synthetic tasks");
  const [error,setError]=useState(""),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true);
  const [runId,setRunId]=useState(""),[task,setTask]=useState(null);
  const [exportedReport,setExportedReport]=useState(null);
  const lifetime=useRef(null);
  const operationLock=useRef(false);
  const selectedOutputSha=summary?.runs.find(r=>r.taskId===runId)?.outputSha256;
  useEffect(()=>{
    const controller=new AbortController();lifetime.current=controller;
    Promise.all([apiClient.getResearchBenchmarks(workspaceId,controller.signal),apiClient.getResearchExperiments(workspaceId,controller.signal)])
      .then(([r,list])=>{if(!controller.signal.aborted){setRegistry(r);setExperiments(list);}})
      .catch(err=>{if(!controller.signal.aborted)setError(err.message);})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[workspaceId]);
  useEffect(()=>{
    setSummary(null);setRunId("");setTask(null);setExportedReport(null);
    if(!selected)return;
    const controller=new AbortController();let timer;
    async function refresh(){
      try {const data=await apiClient.getResearchExperiment(selected,workspaceId,controller.signal);
        if(!controller.signal.aborted){setSummary(data);setError("");if(data.status==="incomplete")timer=setTimeout(refresh,3000);}}
      catch(err){if(!controller.signal.aborted)setError(err.message);}
    }
    refresh();return ()=>{controller.abort();clearTimeout(timer);};
  },[selected,workspaceId]);
  useEffect(()=>{
    setTask(null);if(!runId)return;
    const controller=new AbortController();
    apiClient.getResearchRun(runId,workspaceId,controller.signal).then(t=>{if(!controller.signal.aborted)setTask(t);}).catch(err=>{if(!controller.signal.aborted)setError(err.message);});
    return ()=>controller.abort();
  },[runId,workspaceId,selectedOutputSha]);
  async function act(operation){
    if(operationLock.current)return;operationLock.current=true;setBusy(true);setError("");
    try {const result=await operation();if(!lifetime.current.signal.aborted){setSelected(result.experimentId);setSummary(result);setExperiments(await apiClient.getResearchExperiments(workspaceId,lifetime.current.signal));}}
    catch(err){if(!lifetime.current.signal.aborted)setError(err.outcomeUnknown ? `Creation acknowledgement unavailable. Reload experiments before retrying. ${err.message}` : err.message);}
    finally{operationLock.current=false;if(!lifetime.current.signal.aborted)setBusy(false);}
  }
  async function start(event){event.preventDefault();try{researchPayload(cases,modes,repetitions,purpose);setConfirming(true);}catch(err){setError(err.message);}}
  async function confirmStart(){setConfirming(false);await act(()=>apiClient.createResearchExperiment(researchPayload(cases,modes,repetitions,purpose),workspaceId));setView("saved");}
  async function saveReview(payload){
    if(operationLock.current)return;operationLock.current=true;setBusy(true);
    try{const next=await apiClient.reviewResearchRun(selected,runId,payload,workspaceId);if(!lifetime.current.signal.aborted){setSummary(next);setTask(await apiClient.getResearchRun(runId,workspaceId,lifetime.current.signal));}}
    finally{operationLock.current=false;if(!lifetime.current.signal.aborted)setBusy(false);}
  }
  async function download(){
    try{const saved=await apiClient.exportResearchExperiment(selected,workspaceId,lifetime.current.signal);if(lifetime.current.signal.aborted)return;
      setExportedReport(saved);
      const url=URL.createObjectURL(new Blob([JSON.stringify(saved,null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download=selected+"-report.json";a.click();URL.revokeObjectURL(url);}
    catch(err){if(!lifetime.current.signal.aborted)setError(err.message);}
  }
  const currentRun=summary?.runs.find(r=>r.taskId===runId);
  return <main className="research-lab"><h1>Research Lab</h1><p>Compare how agents solve the same task, inspect saved answers, and evaluate evidence. Start with a historical example or prepare your own experiment.</p>
    <nav className="research-choices" aria-label="Research experiences"><button aria-pressed={view === "sample"} onClick={()=>setView("sample")}>Explore a sample experiment</button><button aria-pressed={view === "new"} onClick={()=>setView("new")}>Set up a new experiment</button><button aria-pressed={view === "saved"} onClick={()=>setView("saved")}>Your saved experiments ({experiments.length})</button></nav>
    {view === "welcome" && <section className="research-new"><h2>New to Research Lab?</h2><p>Explore 42 historical fixture trials without using an AI provider. Your real workspace history and new experiments stay separate from this demonstration.</p><button onClick={()=>setView("sample")}>Open historical sample</button></section>}
    {view === "sample" && <ResearchSample/>}
    {loading && <p role="status">Loading workspace research…</p>}{error && <p role="alert">{error}</p>}
    {view === "new" && registry && <section className="research-new"><h2>Start a comparison</h2><ol className="research-steps"><li>Choose synthetic tasks.</li><li>Choose ways to solve them.</li><li>Review trial count and provider use.</li></ol><p>Single uses one Direct agent; Fixed runs the specialist pipeline; Adaptive selects specialists for the case. Choose synthetic benchmark cases below.</p><form onSubmit={start} className="research-config">
      <details><summary>Benchmark protocol</summary><p>Benchmark suite · version {registry.version}</p></details>
      <label>Experiment purpose<input required maxLength={600} value={purpose} disabled={busy} onChange={e=>setPurpose(e.target.value)}/></label>
      <fieldset disabled={busy}><legend>Benchmark cases</legend>{registry.cases.map(c=><label key={c.id} className="research-case"><input type="checkbox" checked={cases.includes(c.id)} onChange={e=>setCases(e.target.checked?[...cases,c.id]:cases.filter(id=>id!==c.id))}/><span><strong>{c.title}</strong><br/>{c.rationale}<details><summary>Directive, source and criteria</summary><pre>{JSON.stringify(c,null,2)}</pre></details></span></label>)}</fieldset>
      <fieldset disabled={busy}><legend>Execution modes</legend>{MODES.map(mode=><label key={mode}><input type="checkbox" checked={modes.includes(mode)} onChange={e=>setModes(e.target.checked?[...modes,mode]:modes.filter(m=>m!==mode))}/>{modeDescriptions[mode]}</label>)}</fieldset>
      <label>Repetitions (1–5, at most 45 runs)<input type="number" min="1" max="5" required disabled={busy} value={repetitions} onChange={e=>setRepetitions(Number(e.target.value))}/></label>
      <p>{cases.length*modes.length*repetitions} planned runs. Sequential execution; mode order rotates between repetitions.</p>
      {!registry.executionEnabled && <p>New experiment execution is disabled by the server. An operator must authorize provider usage and enable it. You can still explore the historical sample and inspect saved experiments.</p>}
      {registry.executionEnabled && <p>{registry.configuration.evidenceKind === "deterministic_fixture" ? "Local fixture provider configured. These runs validate the evaluation machinery." : "Starting an experiment invokes the configured live provider."}</p>}
      <button disabled={busy||!registry.executionEnabled||!cases.length||!modes.length||cases.length*modes.length*repetitions>45}>Review experiment before starting</button>
    </form></section>}
    {view === "new" && registry && <p role="status">{registry.configuration.evidenceKind === "deterministic_fixture" ? "Deterministic fixture environment — no live model conclusions." : "Provider environment"} · benchmark suite {registry.version}</p>}
    {view === "saved" && <section><h2>Your saved experiments</h2>{!loading&&!experiments.length&&<p>No experiments yet in this workspace. Explore the historical sample now, or set up a new experiment when execution is authorized. Saved runs will appear here after admission.</p>}
      <label>Experiment<select aria-label="Experiment" value={selected} onChange={e=>setSelected(e.target.value)} disabled={busy}><option value="">Select experiment</option>{experiments.map(e=><option key={e.experimentId} value={e.experimentId}>{e.purpose} · {e.experimentId} · {e.recordedRuns}/{e.expectedRuns} runs</option>)}</select></label>
      <button type="button" disabled={busy||!selected} onClick={()=>act(async()=>apiClient.getResearchExperiment(selected,workspaceId,lifetime.current.signal))}>Reload results</button>
      <button type="button" disabled={busy||!summary||!registry?.executionEnabled} onClick={()=>act(()=>apiClient.rerunResearchExperiment(selected,workspaceId))}>Rerun same configuration</button>
      <button type="button" disabled={!summary} onClick={download}>Export evidence report</button>
      <ExportedResearchReport report={exportedReport}/>
      {summary && <section aria-label="Experiment summary"><h2>{experiments.find(e=>e.experimentId===selected)?.purpose ?? "Selected experiment"}</h2><p>Modes: {summary.configuration.modes?.join(", ") ?? [...new Set(summary.runs.map(r=>r.mode))].join(", ")}</p><p>Benchmarks: {new Set(summary.runs.map(r=>r.benchmarkId)).size} · Repetitions: {Math.max(0,...summary.runs.map(r=>r.trialNumber))}</p><p>Trial progress: {summary.runs.filter(r=>["completed","failed"].includes(r.status)).length} / {summary.runs.length}</p></section>}
      <ComparisonTable summary={summary}/>
      {summary && <><h3>Individual trials and routing</h3><label>Trial<select aria-label="Trial" value={runId} onChange={e=>setRunId(e.target.value)} disabled={busy}><option value="">Select run</option>{summary.runs.map(r=><option key={r.taskId} value={r.taskId}>{r.benchmarkId} · {r.mode} · trial {r.trialNumber} · {r.status}</option>)}</select></label></>}
      {currentRun&&<ResearchRun key={runId} run={currentRun} task={task} busy={busy} onReview={saveReview} onInspect={()=>{if(task&&acceptRun(task)){selectTask(task.id);setActivePage("live");}}}/>}
    </section>}
    {confirming && <Modal title="Review experiment" onClose={()=>setConfirming(false)} canDismiss={!busy}><p>{cases.length} cases × {modes.length} modes × {repetitions} repetitions = <strong>{cases.length*modes.length*repetitions} trials</strong>.</p><p>{registry?.configuration.evidenceKind === "deterministic_fixture" ? "This local test environment uses a fixture provider. It cannot establish live model quality." : "This invokes the configured AI provider. Multiple stage calls may be made; usage and cost are not estimated here."}</p><p>Results will be saved to this workspace under Your saved experiments. Starting does not approve or publish any result.</p><button disabled={busy || !registry?.executionEnabled} onClick={confirmStart}>Start {cases.length*modes.length*repetitions} trials</button></Modal>}
  </main>;
}
export default function ResearchLab(){const {activeWorkspaceId}=useWorkspace();return activeWorkspaceId?<ResearchWorkspace key={activeWorkspaceId} workspaceId={activeWorkspaceId}/>:<p>Select an available workspace to view research.</p>;}
