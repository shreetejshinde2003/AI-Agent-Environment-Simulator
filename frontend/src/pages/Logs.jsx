import { useSimulation } from "../context/SimulationContext";
import SimulationTimeline from "../components/dashboard/SimulationTimeline";
import Card from "../components/common/Card";
export default function Logs() {
  const {timeline, activity} = useSimulation();
  return <div className="workspace-stack"><h1>Execution log</h1>
    <Card title="Authoritative execution events"><SimulationTimeline timeline={timeline}/></Card>
    <Card title="Agent activity">{!activity.length ? <p className="empty-note">No activity yet.</p> :
      <ol className="event-timeline">{activity.map(a => <li key={a.id}>
        <time>{new Date(a.timestamp).toLocaleTimeString()}</time><span>{a.agentId}: {a.text}</span></li>)}</ol>}</Card></div>;
}
