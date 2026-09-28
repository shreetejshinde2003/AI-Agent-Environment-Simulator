import "./SimulationInfoPanel.css";
export default function SimulationInfoPanel({stats}) {
  const rows = [
    ["Simulations", stats.totalTasks ?? 0], ["Completed", stats.completedTasks ?? 0],
    ["Failed", stats.failedTasks ?? 0], ["Active executions", stats.activeAgents ?? 0],
    ["Agent calls", stats.totalAgentExecutions ?? 0], ["Handoffs", stats.totalMessages ?? 0],
  ];
  return <div className="sim-info-panel"><span className="sim-info-title">Workspace totals</span>
    {rows.map(([label, value]) => <div key={label} className="sim-info-row">
      <span className="sim-info-label">{label}</span><span className="sim-info-value">{value}</span></div>)}</div>;
}
