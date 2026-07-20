import { Handle, Position } from "reactflow";
import "./AgentNode.css";

/**
 * AgentNode — custom React Flow node representing one agent as a
 * colored circle with a status label, matching the reference image's
 * "Research Agent / Active" style nodes.
 *
 * React Flow passes `data` as whatever object you gave the node when
 * building the node list (see AgentRelationshipGraph.jsx) — here we
 * expect { label, status, color }.
 */
export default function AgentNode({ data }) {
  const { label, status, color } = data;

  return (
    <div className="agent-node">
      {/* Handles are invisible connection points React Flow needs on
          every side so edges can attach from any direction. */}
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />

      <div className="agent-node-circle" style={{ borderColor: color, background: `${color}1a` }}>
        <span className="agent-node-dot" style={{ background: color }} />
      </div>
      <div className="agent-node-label">{label}</div>
      <div className={`agent-node-status agent-node-status-${status}`}>{status}</div>
    </div>
  );
}
