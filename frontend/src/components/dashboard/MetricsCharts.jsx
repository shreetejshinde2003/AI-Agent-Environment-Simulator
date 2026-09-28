import Card from "../common/Card";
function Bars({items, unit = ""}) {
  const values = items.filter(item => item.value != null);
  if (!values.length) return <p className="empty-note">No measured execution data yet.</p>;
  const max = Math.max(1, ...values.map(item => item.value));
  return <div className="chart-bars">{values.map(item => <div key={item.label} className="chart-row">
    <span>{item.label}</span><div className="bar-track"><div style={{width: (item.value/max*100) + "%"}}/></div>
    <output>{Number(item.value.toFixed(2)).toLocaleString()}{unit}</output>
  </div>)}</div>;
}
export default function MetricsCharts({metrics}) {
  const agents = metrics?.agents ?? [];
  const history = metrics?.history ?? [];
  const charts = [
    ["Token usage by agent", agents.map(a => ({label: a.agentId, value: a.measuredCalls ? a.totalTokens : null})), ""],
    ["Average response time", agents.map(a => ({label: a.agentId, value: a.averageLatency})), "s"],
    ["Agent invocation counts", agents.filter(a => a.calls).map(a => ({label: a.agentId, value: a.calls})), ""],
    ["Recent simulation durations", history.filter(r => r.duration != null).slice(-10).map(r => ({
      label: new Date(r.createdAt).toLocaleString() + " · " + r.id.slice(-4) + " · " + r.status, value: r.duration})), "s"],
  ];
  return <section className="workspace-stack"><h2>Persisted execution metrics</h2>
    {!history.length && <p className="empty-note">No simulation data yet.</p>}
    <div className="run-grid equal">{charts.map(([title, items, unit]) => <Card title={title} key={title}>
      <Bars items={items} unit={unit}/></Card>)}</div>
  </section>;
}
