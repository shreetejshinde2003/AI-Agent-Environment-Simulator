export default function StatsCardRow({stats = {}}) {
  const cards = [
    ["Simulations", stats.totalTasks ?? 0], ["Completed", stats.completedTasks ?? 0],
    ["Failed", stats.failedTasks ?? 0], ["Success rate", stats.successRatePercent == null ? "—" : stats.successRatePercent.toFixed(1) + "%"],
    ["Average duration", stats.avgResponseTimeSeconds == null ? "—" : stats.avgResponseTimeSeconds.toFixed(2) + "s"],
    ["Measured tokens", stats.measuredExecutions ? stats.totalTokens.toLocaleString() : "—"],
  ];
  return <div className="metrics-grid">{cards.map(([label, value]) =>
    <div className="metric-card" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>;
}
