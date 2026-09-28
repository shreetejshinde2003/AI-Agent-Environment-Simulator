export default function MessageFlowFeed({messages = []}) {
  if (!messages.length) return <p className="empty-note">No agent handoffs yet. Individual-agent runs have no handoffs.</p>;
  return <div className="message-list">{messages.map(message => <details key={message.id} className="handoff">
    <summary><strong>{message.fromAgentId} → {message.toAgentId}</strong>
      <span>{message.outputKey} · {new Date(message.timestamp).toLocaleTimeString()}</span>
      <p>{message.content.slice(0, 150)}{message.content.length > 150 ? "…" : ""}</p>
    </summary>
    <p className="muted">{message.kind} · {message.content.length} characters · {message.id}</p>
    <pre>{message.content}</pre>
  </details>)}</div>;
}
