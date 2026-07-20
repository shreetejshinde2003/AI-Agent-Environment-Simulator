import { formatDuration } from "../../utils/formatTime";
import "./SimulationInfoPanel.css";

/**
 * SimulationInfoPanel — the small info block in the sidebar showing
 * Simulation ID, Status, Start Time, Duration, and agent/task counts.
 * Rendered inside layout/Sidebar.jsx, but kept as its own component
 * (in components/dashboard/, not layout/) since it's simulation DATA,
 * not navigation chrome — Sidebar stays a dumb layout piece.
 *
 * Handles the "offline" state explicitly: stats.status === "offline"
 * means no backend/simulation is actually running (see
 * hooks/useSimulationData.js's EMPTY_STATS) — every field falls back
 * to a plain "—" instead of a fabricated value or a NaN from dividing
 * by zero.
 *
 * Props:
 *  - stats: SimulationStats  (see services/mockData.js)
 */
export default function SimulationInfoPanel({ stats }) {
  const isOffline = stats.status === "offline";

  const completedPercent =
    stats.totalTasks > 0 ? Math.round((stats.completedTasks / stats.totalTasks) * 100) : null;

  const rows = [
    { label: "Simulation ID", value: stats.simulationId ?? "—", mono: true },
    { label: "Status", value: stats.status, statusDot: !isOffline },
    {
      label: "Start Time",
      value: stats.startTime ? new Date(stats.startTime).toLocaleString() : "—",
    },
    { label: "Duration", value: formatDuration(stats.durationSeconds) },
    { label: "Total Agents", value: stats.totalAgents },
    { label: "Total Tasks", value: stats.totalTasks },
    {
      label: "Completed",
      value: completedPercent === null ? "0" : `${stats.completedTasks} (${completedPercent}%)`,
    },
    { label: "Active Agents", value: `${stats.activeAgents} / ${stats.totalAgents}` },
  ];

  return (
    <div className="sim-info-panel">
      <span className="sim-info-title">Simulation Info</span>
      {rows.map((row) => (
        <div key={row.label} className="sim-info-row">
          <span className="sim-info-label">{row.label}</span>
          <span className={`sim-info-value${row.mono ? " is-mono" : ""}`}>
            {row.statusDot && <span className="sim-info-status-dot" />}
            {isOffline && row.label === "Status" && (
              <span className="sim-info-status-dot sim-info-status-dot-offline" />
            )}
            {row.value}
          </span>
        </div>
      ))}
    </div>
  );
}
