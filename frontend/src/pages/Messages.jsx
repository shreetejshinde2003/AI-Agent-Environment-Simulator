import { useSimulation } from "../context/SimulationContext";
import MessageFlowFeed from "../components/dashboard/MessageFlowFeed";
import Card from "../components/common/Card";
export default function Messages() {
  const {messages, selectedTask} = useSimulation();
  return <div className="workspace-stack"><h1>Message flow</h1>
    <p className="muted">Exact agent outputs handed to the next stage · {selectedTask?.id ?? "No simulation selected"}</p>
    <Card title="Agent communication"><MessageFlowFeed messages={messages}/></Card></div>;
}
