export default function SimulationTimeline({timeline = [], limit}) {
  const events = limit == null ? timeline : timeline.slice(0, limit);
  if (!events.length) return <p className="empty-note">No execution events yet.</p>;
  return <ol className="event-timeline">{events.map(event => <li key={event.id}
    className={event.type.includes("failed") ? "failed" : ""}>
    <time dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleTimeString()}</time>
    <span>{event.text}</span>
  </li>)}</ol>;
}
