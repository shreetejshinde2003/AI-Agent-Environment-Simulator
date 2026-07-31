import { useState } from "react";
import { Users, ClipboardPlus, Download, Trash2 } from "lucide-react";
import { useSimulation } from "../../context/SimulationContext";
import CreateTaskModal from "./CreateTaskModal";
import AddAgentModal from "./AddAgentModal";
import "./QuickActions.css";

/**
 * QuickActions — the 4-button grid at the bottom right: Add Agent,
 * Create Task, Export Logs, Clear All.
 *
 * Add Agent / Create Task open real forms wired to the backend (see
 * CreateTaskModal.jsx / AddAgentModal.jsx) — both endpoints already
 * exist and work. Export Logs / Clear All stay TODO: there's no
 * backend endpoint for either yet (stats_tracker.py has a reserved
 * `reset()` method for Clear All, but nothing calls it).
 */
export default function QuickActions() {
  const { agents, connectionStatus, isDemoMode } = useSimulation();
  const [openModal, setOpenModal] = useState(null); // null | "task" | "agent"

  const canAct = isDemoMode || connectionStatus === "connected";

  const handleExportLogs = () => console.log("TODO: export logs as CSV/JSON — no backend endpoint yet");
  const handleClearAll = () => console.log("TODO: wire to stats_tracker.reset() — not exposed via a route yet");

  const actions = [
    { label: "Add Agent", icon: Users, onClick: () => setOpenModal("agent"), disabled: !canAct },
    { label: "Create Task", icon: ClipboardPlus, onClick: () => setOpenModal("task"), disabled: !canAct },
    { label: "Export Logs", icon: Download, onClick: handleExportLogs, disabled: !canAct },
    { label: "Clear All", icon: Trash2, onClick: handleClearAll, danger: true, disabled: !canAct },
  ];

  return (
    <>
      <div className="quick-actions-grid">
        {actions.map(({ label, icon: Icon, onClick, danger, disabled }) => (
          <button
            key={label}
            type="button"
            className={`quick-action-btn${danger ? " is-danger" : ""}`}
            onClick={onClick}
            disabled={disabled}
            title={disabled ? "Connect the backend to use this" : undefined}
          >
            <Icon size={18} strokeWidth={2} />
            <span>{label}</span>
          </button>
        ))}
      </div>

      {openModal === "task" && (
        <CreateTaskModal agents={agents} onClose={() => setOpenModal(null)} />
      )}
      {openModal === "agent" && (
        <AddAgentModal onClose={() => setOpenModal(null)} />
      )}
    </>
  );
}
