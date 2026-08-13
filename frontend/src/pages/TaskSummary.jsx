import { useMemo, useState } from "react";
import { useSimulation } from "../context/SimulationContext";
import TaskDetailsPanel from "../components/dashboard/TaskDetailsPanel";
import Card from "../components/common/Card";
import ConnectionBadge from "../components/common/ConnectionBadge";
import "./TaskSummary.css";

/**
 * TaskSummary — full task table/board, built from useSimulation().tasks.
 * Filterable by status/priority; clicking a row opens the same
 * TaskDetailsPanel used on the Live Simulation page, in a side drawer.
 */

function getTaskId(task, i) {
  return task?.id ?? task?.taskId ?? `task-${i}`;
}
function getTaskTitle(task) {
  return task?.title ?? task?.name ?? "Untitled Task";
}
function getTaskStatus(task) {
  return (task?.status ?? "unknown").toString().toLowerCase();
}
function getTaskPriority(task) {
  return (task?.priority ?? "normal").toString().toLowerCase();
}
function getTaskAgentId(task) {
  return task?.assignedAgentId ?? task?.agentId ?? task?.ownerId ?? null;
}

function resolveAgentName(agentId, agents) {
  if (!agentId) return "Unassigned";
  const agent = agents.find((a) => (a?.id ?? a?.agentId) === agentId);
  return agent?.name ?? agent?.id ?? agentId;
}

export default function TaskSummary() {
  const { tasks = [], agents = [], connectionStatus, isDemoMode } = useSimulation();
  const [statusFilter, setStatusFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [selectedTask, setSelectedTask] = useState(null);

  const statusOptions = useMemo(
    () => ["all", ...new Set(tasks.map((t) => getTaskStatus(t)))],
    [tasks]
  );
  const priorityOptions = useMemo(
    () => ["all", ...new Set(tasks.map((t) => getTaskPriority(t)))],
    [tasks]
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return tasks.filter((task) => {
      const status = getTaskStatus(task);
      const priority = getTaskPriority(task);
      const title = getTaskTitle(task).toLowerCase();
      const matchesStatus = statusFilter === "all" || status === statusFilter;
      const matchesPriority = priorityFilter === "all" || priority === priorityFilter;
      const matchesQuery = !q || title.includes(q);
      return matchesStatus && matchesPriority && matchesQuery;
    });
  }, [tasks, statusFilter, priorityFilter, search]);

  return (
    <div className="task-summary-page">
      <Card
        title={`Tasks (${filtered.length}${
          filtered.length !== tasks.length ? ` of ${tasks.length}` : ""
        })`}
        headerRight={
          <ConnectionBadge connectionStatus={connectionStatus} isDemoMode={isDemoMode} compact />
        }
      >
        <div className="task-toolbar">
          <input
            type="text"
            className="task-search"
            placeholder="Search tasks…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            className="task-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            {statusOptions.map((s) => (
              <option key={s} value={s}>
                {s === "all" ? "All statuses" : s}
              </option>
            ))}
          </select>
          <select
            className="task-select"
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
          >
            {priorityOptions.map((p) => (
              <option key={p} value={p}>
                {p === "all" ? "All priorities" : p}
              </option>
            ))}
          </select>
        </div>

        {tasks.length === 0 ? (
          <div className="task-empty">
            No tasks yet — they'll show up here once a simulation starts.
          </div>
        ) : filtered.length === 0 ? (
          <div className="task-empty">No tasks match your filters.</div>
        ) : (
          <div className="task-table">
            <div className="task-row task-row-head">
              <span className="task-col-title">Task</span>
              <span className="task-col-status">Status</span>
              <span className="task-col-priority">Priority</span>
              <span className="task-col-agent">Agent</span>
            </div>
            <div className="task-body">
              {filtered.map((task, i) => {
                const id = getTaskId(task, i);
                return (
                  <button
                    type="button"
                    className="task-row task-row-clickable"
                    key={id}
                    onClick={() => setSelectedTask(task)}
                  >
                    <span className="task-col-title">{getTaskTitle(task)}</span>
                    <span className="task-col-status">
                      <span className="task-pill" data-status={getTaskStatus(task)}>
                        {getTaskStatus(task)}
                      </span>
                    </span>
                    <span className="task-col-priority">
                      <span className="task-pill" data-priority={getTaskPriority(task)}>
                        {getTaskPriority(task)}
                      </span>
                    </span>
                    <span className="task-col-agent">
                      {resolveAgentName(getTaskAgentId(task), agents)}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </Card>

      {selectedTask && (
        <div className="task-drawer-overlay" onClick={() => setSelectedTask(null)}>
          <div className="task-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="task-drawer-header">
              <h3>Task Details</h3>
              <button
                type="button"
                className="task-drawer-close"
                onClick={() => setSelectedTask(null)}
              >
                ✕
              </button>
            </div>
            <TaskDetailsPanel task={selectedTask} agents={agents} />
          </div>
        </div>
      )}
    </div>
  );
}
