import { useState } from "react";
import "./CreateTaskModal.css";

export default function CreateTaskModal({
  isOpen,
  onClose,
  onSubmit,
}) {
  const [directive, setDirective] = useState("");
  const [priority, setPriority] = useState("medium");
  const [assignedAgent, setAssignedAgent] = useState("research");

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();

    onSubmit({
      directive,
      priority,
      assigned_agent_id: assignedAgent,
    });

    setDirective("");
    setPriority("medium");
    setAssignedAgent("research");
  };

  return (
    <div className="task-modal-overlay">
      <div className="task-modal">

        <div className="task-modal-header">
          <h2>Create New Task</h2>

          <button
            className="close-btn"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit}>

          <label>
            Directive
          </label>

          <textarea
            rows="5"
            value={directive}
            onChange={(e)=>setDirective(e.target.value)}
            placeholder="Describe the research task..."
            required
          />

          <label>
            Priority
          </label>

          <select
            value={priority}
            onChange={(e)=>setPriority(e.target.value)}
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>

          <label>
            Assigned Agent
          </label>

          <select
            value={assignedAgent}
            onChange={(e)=>setAssignedAgent(e.target.value)}
          >
            <option value="research">Research Agent</option>
            <option value="web_search">Web Search Agent</option>
            <option value="analysis">Analysis Agent</option>
          </select>

          <div className="modal-buttons">

            <button
              type="button"
              onClick={onClose}
            >
              Cancel
            </button>

            <button
              type="submit"
            >
              Create Task
            </button>

          </div>

        </form>

      </div>
    </div>
  );
}