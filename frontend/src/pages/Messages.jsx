import { useSimulation } from "../context/SimulationContext";
import OutputViewer from "../components/dashboard/OutputViewer";
export default function Messages({contextual = false}) {
  const {messages, selectedTask} = useSimulation();
  return <div className="workspace-stack">{contextual ? <h2>Handoffs</h2> : <h1>Handoffs</h1>}
    <p className="muted">Persisted agent outputs are evidence. Downstream prompts use a bounded stage contract; this is not the exact model prompt.</p>
    {!messages.length && <p className="empty-note">{selectedTask ? "No handoffs recorded. Single runs have no agent handoffs." : "Choose a run to inspect handoffs."}</p>}
    {messages.map(message => <article key={message.id}><h3>{message.fromAgentId} → {message.toAgentId}</h3>
      <p>{message.outputKey ?? message.kind} · Recorded · <time dateTime={message.timestamp}>{new Date(message.timestamp).toLocaleString()}</time></p>
      <OutputViewer text={message.content} intermediate label="Handoff output"/>
      <details><summary>Technical details</summary><code>{message.id}</code></details>
    </article>)}
  </div>;
}
