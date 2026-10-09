import { useState } from "react";
import { useSimulation } from "../../context/SimulationContext";
import CreateTaskModal from "./CreateTaskModal";
import Button from "../common/Button";
export default function QuickActions() {
  const [open, setOpen] = useState(false);
  const {agents, connectionStatus} = useSimulation();
  return <>
    <div className="simulation-create-action">
      <Button variant="primary" disabled={connectionStatus !== "connected"} aria-describedby={connectionStatus !== "connected" ? "create-unavailable" : undefined} onClick={() => setOpen(true)}>Create Simulation</Button>
      {connectionStatus !== "connected" && <p id="create-unavailable" className="muted">{connectionStatus === "connecting" ? "Available when your workspace finishes loading." : "Available when the connection recovers."}</p>}
    </div>
    {open && <CreateTaskModal agents={agents} onClose={() => setOpen(false)}/>}
  </>;
}
