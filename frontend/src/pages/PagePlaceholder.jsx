import "./PagePlaceholder.css";

/**
 * PagePlaceholder — shared "not built yet" state for pages beyond
 * Live Simulation. Each real page (TaskSummary, Agents, Messages, Logs,
 * Replay, Settings) currently just renders this with its own title;
 * swap the body out page-by-page as each one gets built.
 */
export default function PagePlaceholder({ title, description }) {
  return (
    <div className="page-placeholder">
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
  );
}
