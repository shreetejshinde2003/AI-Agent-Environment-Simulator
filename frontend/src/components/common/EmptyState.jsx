import "./EmptyState.css";

/**
 * EmptyState — shown by every dashboard panel when there's genuinely
 * no data (no backend connected, or a connected backend with zero
 * agents/tasks/messages so far). This is what makes "0" look
 * intentional instead of like a broken widget.
 *
 * Props:
 *  - icon: lucide-react icon component
 *  - title: short line, e.g. "No agents connected"
 *  - description: one sentence of what needs to happen to see data here
 */
export default function EmptyState({ icon: Icon, title, description }) {
  return (
    <div className="empty-state">
      {Icon && (
        <div className="empty-state-icon">
          <Icon size={26} strokeWidth={1.5} />
        </div>
      )}
      <p className="empty-state-title">{title}</p>
      {description && <p className="empty-state-description">{description}</p>}
    </div>
  );
}
