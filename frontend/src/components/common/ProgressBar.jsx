import "./ProgressBar.css";

/**
 * ProgressBar — horizontal fill bar with an optional trailing label.
 * Used in the Task Details panel ("65%") and could be reused for any
 * other percent-complete display.
 */
export default function ProgressBar({ percent, showLabel = true, color }) {
  const clamped = Math.max(0, Math.min(100, percent));

  return (
    <div className="progress-row">
      <div className="progress-track">
        <div
          className="progress-fill"
          style={{ width: `${clamped}%`, background: color || "var(--accent-primary)" }}
        />
      </div>
      {showLabel && <span className="progress-label">{clamped}%</span>}
    </div>
  );
}
