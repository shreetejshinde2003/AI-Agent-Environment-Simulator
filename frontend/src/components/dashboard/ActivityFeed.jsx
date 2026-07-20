import { Activity } from "lucide-react";
import EmptyState from "../common/EmptyState";
import { colorForRole } from "../../utils/colors";
import { formatClockTime } from "../../utils/formatTime";
import "./ActivityFeed.css";

/**
 * ActivityFeed — right-hand "Activity Feed" list: short, human-readable
 * lines like "Analysis Agent completed data analysis".
 *
 * Props:
 *  - activity: ActivityEvent[]  (see services/mockData.js)
 *  - agents: Agent[]
 */
export default function ActivityFeed({ activity, agents }) {
  const agentsById = Object.fromEntries(agents.map((a) => [a.id, a]));

  if (activity.length === 0) {
    return (
      <EmptyState
        icon={Activity}
        title="No activity yet"
        description="Agent actions will be logged here once a simulation starts."
      />
    );
  }

  return (
    <ul className="activity-feed-list">
      {activity.map((event) => {
        const agent = agentsById[event.agentId];
        const color = agent?.color ?? colorForRole(event.agentId);

        return (
          <li key={event.id} className="activity-feed-item">
            <span className="activity-feed-dot" style={{ background: color }} />
            <p className="activity-feed-text">
              <span style={{ color, fontWeight: 600 }}>{agent?.name ?? event.agentId}</span>{" "}
              {event.text}
            </p>
            <span className="activity-feed-time">{formatClockTime(event.timestamp)}</span>
          </li>
        );
      })}
    </ul>
  );
}
