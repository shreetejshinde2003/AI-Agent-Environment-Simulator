import { useState } from "react";
import { useSimulation } from "../../context/SimulationContext";
import CreateTaskModal from "./CreateTaskModal";
import Button from "../common/Button";
export default function QuickActions() {
  const [open, setOpen] = useState(false);
  const {agents, connectionStatus} = useSimulation();
  return <>
    <Button variant="primary" disabled={connectionStatus !== "connected"} onClick={() => setOpen(true)}>Create Simulation</Button>
    {open && <CreateTaskModal agents={agents} onClose={() => setOpen(false)}/>}
  </>;
}
