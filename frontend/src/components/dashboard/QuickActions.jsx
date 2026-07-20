import { useState } from "react";
import { Users, ClipboardPlus, Download, Trash2 } from "lucide-react";
import "./QuickActions.css";
import CreateTaskModal from "./CreateTaskModal";
import { apiClient } from "../../services/apiClient";

/**
 * QuickActions — the 4-button grid at the bottom right: Add Agent,
 * Create Task, Export Logs, Clear All.
 *
 * These are currently wired to no-op console logs. Hook them up to
 * real handlers (likely via SimulationContext + apiClient.js) once the
 * backend is live — see the RESERVED comments below each button.
 */
export default function QuickActions() {
  const [isTaskModalOpen, setTaskModalOpen] = useState(false);
  // RESERVED: replace with real handlers, e.g.
  //   const { createAgent } = useSimulation();
  //   const handleAddAgent = () => createAgent({ name: "...", role: "..." });
  const handleAddAgent = () => console.log("TODO: open Add Agent form");
  const handleCreateTask = () => {
  setTaskModalOpen(true);
};
  const handleExportLogs = () => console.log("TODO: export logs as CSV/JSON");
  const handleClearAll = () => console.log("TODO: confirm + clear simulation state");

  const actions = [
    { label: "Add Agent", icon: Users, onClick: handleAddAgent },
    { label: "Create Task", icon: ClipboardPlus, onClick: handleCreateTask },
    { label: "Export Logs", icon: Download, onClick: handleExportLogs },
    { label: "Clear All", icon: Trash2, onClick: handleClearAll, danger: true },
  ];

  return (
  <>
    <div className="quick-actions-grid">
      {actions.map(({ label, icon: Icon, onClick, danger }) => (
        <button
          key={label}
          type="button"
          className={`quick-action-btn${danger ? " is-danger" : ""}`}
          onClick={onClick}
        >
          <Icon size={18} strokeWidth={2} />
          <span>{label}</span>
        </button>
      ))}
    </div>

    <CreateTaskModal
  isOpen={isTaskModalOpen}
  onClose={() => setTaskModalOpen(false)}
  onSubmit={async (task) => {
    try {
      console.log("Submitting:", task);

      const response = await apiClient.createTask(task);

      console.log("Backend response:", response);

      alert("Task created successfully!");

      setTaskModalOpen(false);

    } catch (err) {
      console.error(err);
      alert(err.message);
    }
  }}
  />
  </>
);
}
