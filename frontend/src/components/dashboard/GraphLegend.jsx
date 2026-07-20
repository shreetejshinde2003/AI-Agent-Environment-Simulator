import "./GraphLegend.css";

/**
 * GraphLegend — small legend under the graph explaining edge styles:
 * Completed / In Progress / Waiting / Data Flow.
 * Purely presentational — update this list if AgentRelationshipGraph's
 * edge styling logic changes.
 */
const LEGEND_ITEMS = [
  { label: "Completed", color: "var(--status-success)", style: "solid" },
  { label: "In Progress", color: "var(--status-info)", style: "solid" },
  { label: "Waiting", color: "var(--status-warning)", style: "dashed" },
  { label: "Data Flow", color: "var(--text-tertiary)", style: "dashed" },
];

export default function GraphLegend() {
  return (
    <div className="graph-legend">
      {LEGEND_ITEMS.map((item) => (
        <div key={item.label} className="graph-legend-item">
          <span
            className={`graph-legend-line graph-legend-line-${item.style}`}
            style={{ borderColor: item.color }}
          />
          <span>{item.label}</span>
        </div>
      ))}
    </div>
  );
}
