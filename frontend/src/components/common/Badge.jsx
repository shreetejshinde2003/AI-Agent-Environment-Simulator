import "./Badge.css";

/**
 * Badge — small status pill, e.g. "Live", "In Progress", "High".
 *
 * tone controls the color: "success" | "warning" | "danger" | "info" | "neutral"
 */
export default function Badge({ children, tone = "neutral", pulse = false }) {
  return (
    <span className={`badge badge-${tone}${pulse ? " badge-pulse" : ""}`}>
      {pulse && <span className="badge-dot" aria-hidden="true" />}
      {children}
    </span>
  );
}
