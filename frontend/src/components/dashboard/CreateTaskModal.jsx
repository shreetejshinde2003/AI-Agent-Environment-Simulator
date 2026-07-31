import { useState } from "react";
import Modal from "../common/Modal";
import Button from "../common/Button";
import { apiClient } from "../../services/apiClient";
import "./AgentActionForms.css";

/**
 * CreateTaskModal — the real thing QuickActions' "Create Task" button
 * opens. Submits to POST /api/v1/tasks (see backend/app/api/routes/tasks.py),
 * which runs the assigned agent in the background and broadcasts the
 * result over WebSocket — hooks/useLiveSocket.js picks that up and
 * refetches automatically, so this modal doesn't need to do anything
 * clever after a successful submit besides closing itself.
 *
 * Props:
 *  - agents: Agent[]  (for the assignee dropdown)
 *  - onClose: () => void
 */
export default function CreateTaskModal({ agents, onClose }) {
  const [directive, setDirective] = useState("");
  const [assignedAgentId, setAssignedAgentId] = useState(agents[0]?.id ?? "research");
  const [priority, setPriority] = useState("medium");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!directive.trim()) return;

    setIsSubmitting(true);
    setError(null);
    try {
      await apiClient.createTask({ directive: directive.trim(), assignedAgentId, priority });
      onClose();
    } catch (err) {
      // USER-DEFINED: only "research" is a real, implemented agent
      // right now (see backend/app/api/routes/tasks.py's
      // _IMPLEMENTED_AGENTS). Assigning to any other agent will create
      // the task successfully, then it will visibly fail a moment
      // later with "agent not implemented yet" — that's expected until
      // more agents are activated, not a bug in this form.
      setError(err.message || "Failed to create task — is the backend running?");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal title="Create Task" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        {error && <div className="form-error">{error}</div>}

        <div className="form-field">
          <label htmlFor="task-directive">Directive</label>
          <textarea
            id="task-directive"
            value={directive}
            onChange={(e) => setDirective(e.target.value)}
            placeholder="e.g. Summarize recent trends in on-device AI inference"
            autoFocus
          />
        </div>

        <div className="form-field">
          <label htmlFor="task-agent">Assign to</label>
          <select id="task-agent" value={assignedAgentId} onChange={(e) => setAssignedAgentId(e.target.value)}>
            {agents.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}{agent.id !== "research" ? " (not implemented yet)" : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="task-priority">Priority</label>
          <select id="task-priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>

        <div className="form-actions">
          <Button variant="ghost" onClick={onClose} type="button">Cancel</Button>
          <Button variant="primary" type="submit" disabled={isSubmitting || !directive.trim()}>
            {isSubmitting ? "Creating…" : "Create Task"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
