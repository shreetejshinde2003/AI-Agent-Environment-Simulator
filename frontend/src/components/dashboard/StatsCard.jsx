import "./StatsCard.css";

/**
 * StatsCard — one card in the top stat row, e.g. "Agents Active 6/7".
 *
 * Props:
 *  - icon: lucide-react icon component
 *  - iconColor: hex string, tints the icon's background chip
 *  - label: "Agents Active"
 *  - value: "6 / 7"  (kept as a string so callers control formatting)
 */
export default function StatsCard({ icon: Icon, iconColor, label, value }) {
  return (
    <div className="stats-card">
      <div className="stats-card-icon" style={{ background: `${iconColor}22`, color: iconColor }}>
        <Icon size={18} strokeWidth={2} />
      </div>
      <div className="stats-card-text">
        <span className="stats-card-label">{label}</span>
        <span className="stats-card-value">{value}</span>
      </div>
    </div>
  );
}
