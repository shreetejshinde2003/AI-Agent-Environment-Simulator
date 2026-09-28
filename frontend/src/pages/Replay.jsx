import { useState } from "react";
import { useSimulation } from "../context/SimulationContext";
import SimulationTimeline from "../components/dashboard/SimulationTimeline";
import Card from "../components/common/Card";
function History({timeline}) {
  const [index, setIndex] = useState(timeline.length);
  const count = Math.min(index, timeline.length);
  return <Card title="Recorded event history">
    {!timeline.length ? <p className="empty-note">No recorded events yet.</p> : <>
      <p className="muted">Step through saved events. This does not re-run agents or simulate activity.</p>
      <label htmlFor="history-position">Events shown: {count} / {timeline.length}</label>
      <input id="history-position" type="range" min="1" max={timeline.length} value={count} onChange={e => setIndex(Number(e.target.value))}/>
      <SimulationTimeline timeline={timeline} limit={count}/>
    </>}
  </Card>;
}
export default function Replay() {
  const {timeline, selectedTaskId} = useSimulation();
  return <div className="workspace-stack"><h1>Event history</h1><History key={selectedTaskId} timeline={timeline}/></div>;
}
