import { Check, Circle, ClipboardList } from "lucide-react";
import Badge from "../common/Badge";
import ProgressBar from "../common/ProgressBar";
import EmptyState from "../common/EmptyState";
import { colorForRole } from "../../utils/colors";
import { formatDuration } from "../../utils/formatTime";
import "./TaskDetailsPanel.css";

const PRIORITY_TONE = { high: "danger", medium: "warning", low: "info" };
const STATUS_TONE = { in_progress: "info", completed: "success", queued: "neutral", failed: "danger" };
const STATUS_LABEL = { in_progress: "In Progress", completed: "Completed", queued: "Queued", failed: "Failed" };

/**
 * TaskDetailsPanel — shows the currently selected task's directive,
 * assigned agent, timing, and step-by-step progress checklist. This is
 * the panel that answers "what is this agent actually doing right now."
 *
 * Props:
 *  - task: Task | null   (see services/mockData.js for shape)
 *  - agents: Agent[]     (needed to look up the assigned agent's name/color)
 */
export default function TaskDetailsPanel({ task, agents }) {
  if (!task) {
    return (
      <EmptyState
        icon={ClipboardList}
        title="No active task"
        description="Connect the backend and create or start a task to see live details here."
      />
    );
  }

  const assignedAgent = agents.find((a) => a.id === task.assignedAgentId);

  return (
    <div className="task-details">
      <div className="task-details-row">
        <span className="task-details-field-label">Task ID</span>
        <span className="task-details-field-value task-details-id">{task.id}</span>
      </div>

      <div className="task-details-block">
        <span className="task-details-field-label">Directive (Instruction)</span>
        <p className="task-details-directive">{task.directive}</p>
      </div>

      <div className="task-details-block">
        <span className="task-details-field-label">Assigned Agent</span>
        <div className="task-details-agent">
          <span
            className="task-details-agent-dot"
            style={{ background: assignedAgent?.color ?? colorForRole(task.assignedAgentId) }}
          />
          <span>{assignedAgent?.name ?? task.assignedAgentId}</span>
        </div>
      </div>

      <div className="task-details-grid">
        <div>
          <span className="task-details-field-label">Duration</span>
          <span className="task-details-field-value">{formatDuration(task.durationSeconds)}</span>
        </div>
        <div>
          <span className="task-details-field-label">Priority</span>
          <Badge tone={PRIORITY_TONE[task.priority]}>{task.priority}</Badge>
        </div>
        <div>
          <span className="task-details-field-label">Status</span>
          <Badge tone={STATUS_TONE[task.status]}>{STATUS_LABEL[task.status]}</Badge>
        </div>
      </div>

      <div className="task-details-block">
        <span className="task-details-field-label">Output / Progress</span>
        <ProgressBar percent={task.progressPercent} />
      </div>

      <ul className="task-details-checklist">
        {(task.progressSteps ?? []).map((step, i) => (
          <li key={i} className={step.done ? "is-done" : ""}>
            {step.done ? (
              <Check size={14} strokeWidth={2.5} />
            ) : (
              <Circle size={14} strokeWidth={2} />
            )}
            <span>{step.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
