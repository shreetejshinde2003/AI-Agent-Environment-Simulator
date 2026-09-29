import { useState } from "react";
import Modal from "../common/Modal";
import Button from "../common/Button";
import { apiClient } from "../../services/apiClient";
import "./AgentActionForms.css";

// USER-DEFINED: only these roles have a real agent implementation
// behind them right now (backend/app/agents/*_agent.py). Adding an
// agent with a role outside this list still works (it's just a roster
// entry), but assigning tasks to it will fail until that agent file's
// process() is activated.
const KNOWN_ROLES = ["research", "data", "web_search", "analysis", "summarizer", "report"];

/**
 * AddAgentModal — QuickActions' "Add Agent" button. Submits to
 * POST /api/v1/agents (backend/app/api/routes/agents.py), which
 * already works today — this just gives it a real UI instead of the
 * previous console.log stub.
 */
export default function AddAgentModal({ onClose }) {
  const [name, setName] = useState("");
  const [role, setRole] = useState(KNOWN_ROLES[0]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsSubmitting(true);
    setError(null);
    try {
      await apiClient.createAgent({ name: name.trim(), role });
      onClose();
    } catch (err) {
      setError(err.message || "Failed to add agent — is the backend running?");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal title="Add Agent" onClose={onClose} canDismiss={!isSubmitting}>
      <form onSubmit={handleSubmit}>
        {error && <div className="form-error">{error}</div>}

        <div className="form-field">
          <label htmlFor="agent-name">Name</label>
          <input
            id="agent-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Translation Agent"
            autoFocus
          />
        </div>

        <div className="form-field">
          <label htmlFor="agent-role">Role</label>
          <select id="agent-role" value={role} onChange={(e) => setRole(e.target.value)}>
            {KNOWN_ROLES.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>

        <div className="form-actions">
          <Button variant="ghost" onClick={onClose} type="button" disabled={isSubmitting}>Cancel</Button>
          <Button variant="primary" type="submit" disabled={isSubmitting || !name.trim()}>
            {isSubmitting ? "Adding…" : "Add Agent"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
