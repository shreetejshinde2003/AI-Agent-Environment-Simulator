import "./Card.css";

/**
 * Card — the base panel used everywhere on the dashboard (stat cards,
 * the graph panel, task details, activity feed, etc). Keeping this as
 * one component means changing the "panel look" happens in one CSS file.
 */
export default function Card({ title, headerRight, children, className = "" }) {
  return (
    <div className={`card ${className}`}>
      {(title || headerRight) && (
        <div className="card-header">
          {title && <h3 className="card-title">{title}</h3>}
          {headerRight && <div className="card-header-right">{headerRight}</div>}
        </div>
      )}
      <div className="card-body">{children}</div>
    </div>
  );
}
