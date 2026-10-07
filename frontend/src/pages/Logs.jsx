import {useState} from "react";
import { useSimulation } from "../context/SimulationContext";
import {workspaceRecords} from "../utils/eventRecords";
import RecordedText from "../components/dashboard/RecordedText";
export default function Logs({contextual = false, onInspectRecord}) {
  const {selectedTask} = useSimulation();
  const [source,setSource]=useState("all"),[count,setCount]=useState(null);
  const records=workspaceRecords(selectedTask).slice().reverse();
  const filtered=records.filter(row=>source==="all"||row.source===source);
  const shown=Math.min(count??filtered.length,filtered.length);
  return <div className="workspace-stack execution-chronology">{contextual?<h2>Execution events</h2>:<h1>Execution events</h1>}
    <p className="muted">One chronology of recorded events, activity and handoffs. Step through saved records without re-running agents.</p>
    <label>Record source<select value={source} onChange={e=>{setSource(e.target.value);setCount(null);}}><option value="all">All records</option><option value="event">Run events</option><option value="activity">Activity</option><option value="handoff">Handoffs</option></select></label>
    {!!filtered.length&&<label>History position: {shown} / {filtered.length}<input aria-label="History position" type="range" min="1" max={filtered.length} value={shown} onChange={e=>setCount(Number(e.target.value))}/></label>}
    {!filtered.length?<p className="empty-note">{selectedTask?"No recorded entries for this filter yet.":"Choose a run to inspect its execution events."}</p>:
      <ol className="execution-records">{filtered.slice(0,shown).map(row=><li key={row.key}>
        <time dateTime={row.record.timestamp}>{new Date(row.record.timestamp).toLocaleString()}</time><strong>{row.label}</strong><small>{row.source}</small>
        <p>{row.source==="handoff"?`${row.record.fromAgentId} → ${row.record.toAgentId} · ${row.record.outputKey??row.record.kind}`:row.record.text}</p>
        <details><summary>Full recorded detail</summary><RecordedText text={row.record.content??row.record.text} label="event detail"/><code>{row.record.id}</code></details>
        {onInspectRecord&&<button type="button" className="text-button" onClick={()=>onInspectRecord(row.key)}>Inspect record</button>}
      </li>)}</ol>}
  </div>;
}
