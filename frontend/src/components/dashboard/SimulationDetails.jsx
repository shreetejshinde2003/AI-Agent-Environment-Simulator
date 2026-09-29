import { useSimulation } from "../../context/SimulationContext";
import Card from "../common/Card";
import AgentRelationshipGraph from "./AgentRelationshipGraph";
import SimulationTimeline from "./SimulationTimeline";
import MessageFlowFeed from "./MessageFlowFeed";
import TaskDetailsPanel from "./TaskDetailsPanel";
import { runTitle } from "../../utils/runs";
export default function SimulationDetails({task}) {
  const {agents} = useSimulation();
  return <div className="workspace-stack">
    <div className="run-grid">
      <Card title={task ? "Execution graph · " + runTitle(task) : "Pipeline preview · no execution yet"}>
        <AgentRelationshipGraph key={task?.id ?? "preview"} task={task} agents={agents}/>
      </Card>
      <Card title="Simulation details & final result"><TaskDetailsPanel task={task}/></Card>
    </div>
    <div className="run-grid equal">
      <Card title="Execution timeline"><SimulationTimeline timeline={task?.events ?? []}/></Card>
      <Card title="Agent handoffs"><MessageFlowFeed messages={task?.messages ?? []}/></Card>
    </div>
    <Card title="Activity">
      {!task?.activities?.length ? <p className="empty-note">No activity yet.</p> :
        <details><summary>{task.activities.length} recorded activities</summary><ol className="event-timeline">
          {task.activities.map(a => <li key={a.id}><time>{new Date(a.timestamp).toLocaleTimeString()}</time>
            <span>{a.agentId}: {a.text}</span></li>)}</ol></details>}
    </Card>
  </div>;
}
