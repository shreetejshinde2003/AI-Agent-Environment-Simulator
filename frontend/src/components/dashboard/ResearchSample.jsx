import {useEffect, useState} from "react";
import {loadResearchSample, modeDescriptions} from "../../utils/researchSample";
import {measured} from "../../utils/research";
import OutputViewer from "./OutputViewer";
export function SampleEvidence({report, selectedId, onSelect}) {
  const summary=report.observedEvidence;
  const entry=report.runEvidence.find(item=>item.task.id===selectedId) ?? report.runEvidence[0];
  const {task,metrics}=entry;
  const cases=[...new Map(report.runEvidence.map(item=>[item.task.research.benchmark.id,item.task.research.benchmark])).values()];
  return <section className="research-sample" aria-label="Historical sample experiment">
    <p className="sample-label" role="status">Historical sample · deterministic fixture · read-only</p>
    <h2>Explore a saved comparison</h2><p>Seven synthetic assignments were compared in three modes, with two trials per case and mode: <strong>{report.runEvidence.length} saved trials</strong>. These are historical test responses, not a new experiment or real Google/Groq execution.</p>
    <p>Recorded {new Date(summary.createdAt).toLocaleString()}. The original report is preserved; viewing it makes no provider request and saves nothing to your workspace.</p>
    <ul>{Object.values(modeDescriptions).map(text=><li key={text}>{text}</li>)}</ul>
    <details><summary>What was asked? Seven benchmark inputs</summary>{cases.map(c=><article key={c.id}><h3>{c.title}</h3><p>{c.directive}</p><blockquote>{c.source}</blockquote><p>{c.rationale}</p><details><summary>Reference checks</summary><pre>{JSON.stringify(c.checks,null,2)}</pre></details></article>)}</details>
    <h3>Recorded descriptive results</h3><p>These checks demonstrate orchestration and measurement. Fixture success is not model accuracy; recorded time is local test time, not provider latency. No cost, statistical significance or winning mode is established.</p>
    <div className="research-table-scroll" tabIndex={0} aria-label="Historical comparison"><table><caption>Original case/mode summaries · measured trials only</caption><thead><tr><th>Case / mode</th><th>Completed trials</th><th>Recorded success</th><th>Reference checks</th><th>Stage starts</th></tr></thead><tbody>{summary.cells.map(c=><tr key={c.benchmarkId+c.mode}><th scope="row">{cases.find(x=>x.id===c.benchmarkId)?.title} / {c.mode}</th><td>{c.terminalTrials}/{c.expectedTrials}</td><td>{measured(c.successRate,true)}</td><td>{measured(c.deterministicQuality.mean,true)} (n={c.deterministicQuality.n})</td><td>{measured(c.agentCalls.mean)}</td></tr>)}</tbody></table></div>
    <label>Inspect a stored trial<select aria-label="Inspect a stored trial" value={task.id} onChange={e=>onSelect(e.target.value)}>{summary.runs.map(r=><option key={r.taskId} value={r.taskId}>{cases.find(c=>c.id===r.benchmarkId)?.title} · {r.mode} · trial {r.trialNumber}</option>)}</select></label>
    <h3>Original saved answer</h3><p>{modeDescriptions[metrics.mode]} · trial {metrics.trialNumber} · {metrics.status}</p>
    <OutputViewer key={task.id} text={task.output} directive={task.directive}/>
    <details><summary>Evidence behind this answer</summary><p>Input: {task.directive}</p><p>Recorded stages: {task.stages.map(s=>`${s.agentId}: ${s.status}`).join(" → ")}</p>
      <p>Reference check score: {measured(metrics.deterministicQuality?.score,true)}. Human score: {measured(metrics.humanScore)}. Cost: {measured(metrics.cost)}.</p>
      <pre>{JSON.stringify({taskId:task.id,provenance:task.provenance,routePlan:task.routePlan,stages:task.stages},null,2)}</pre></details>
    <details><summary>Provenance and limitations</summary><p>Source: docs/acceptance/phase10-fixture-report.json · research-report-v1. Fixture implementation fingerprint: {summary.configuration.fixtureSha256}</p><ul>{summary.limitations.map(text=><li key={text}>{text}</li>)}</ul><p>{report.researchConclusion}</p></details>
    <a className="btn btn-default" href="/examples/research-fixture-report.json" download="historical-fixture-report.json">Download original sample evidence</a>
  </section>;
}
export default function ResearchSample() {
  const [report,setReport]=useState(null),[error,setError]=useState(""),[selected,setSelected]=useState(""),[retry,setRetry]=useState(0);
  useEffect(()=>{const controller=new AbortController();setError("");loadResearchSample(controller.signal).then(data=>{if(!controller.signal.aborted)setReport(data);}).catch(err=>{if(!controller.signal.aborted)setError(err.message);});return()=>controller.abort();},[retry]);
  if(error)return <section><p role="alert">{error}</p><button onClick={()=>setRetry(v=>v+1)}>Reload sample</button></section>;
  if(!report)return <p role="status">Loading historical sample evidence…</p>;
  return <SampleEvidence report={report} selectedId={selected} onSelect={setSelected}/>;
}
