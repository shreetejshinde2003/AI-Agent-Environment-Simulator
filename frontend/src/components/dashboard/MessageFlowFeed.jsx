import { ArrowRight, MessagesSquare } from "lucide-react";
import Avatar from "../common/Avatar";
import Badge from "../common/Badge";
import EmptyState from "../common/EmptyState";
import { colorForRole } from "../../utils/colors";
import { formatClockTime } from "../../utils/formatTime";
import "./MessageFlowFeed.css";

/**
 * MessageFlowFeed — "Message Flow (Live)" card. Shows the most recent
 * agent-to-agent messages: who sent it, who received it, and the
 * message content itself.
 *
 * Props:
 *  - messages: Message[]  (see services/mockData.js)
 *  - agents: Agent[]      (looked up for name/color per message)
 */
export default function MessageFlowFeed({ messages, agents }) {
  const agentsById = Object.fromEntries(agents.map((a) => [a.id, a]));

  if (messages.length === 0) {
    return (
      <EmptyState
        icon={MessagesSquare}
        title="No messages yet"
        description="Agent-to-agent messages will appear here once a simulation is running."
      />
    );
  }

  return (
    <ul className="message-flow-list">
      {messages.map((msg) => {
        const from = agentsById[msg.fromAgentId];
        const to = agentsById[msg.toAgentId];

        return (
          <li key={msg.id} className="message-flow-item">
            <Avatar name={from?.name} color={from?.color ?? colorForRole(msg.fromAgentId)} />

            <div className="message-flow-body">
              <div className="message-flow-header">
                <span className="message-flow-from">{from?.name ?? msg.fromAgentId}</span>
                <Badge tone={msg.kind === "request" ? "info" : "success"}>{msg.kind}</Badge>
                <ArrowRight size={13} className="message-flow-arrow" />
                <span className="message-flow-to">{to?.name ?? msg.toAgentId}</span>
              </div>
              <p className="message-flow-content">{msg.content}</p>
            </div>

            <span className="message-flow-time">{formatClockTime(msg.timestamp)}</span>
          </li>
        );
      })}
    </ul>
  );
}
