import { useMemo } from "react";
import ReactFlow, { Background, Controls, MarkerType } from "reactflow";
import "reactflow/dist/style.css";
import { Network } from "lucide-react";
import AgentNode from "./AgentNode";
import GraphLegend from "./GraphLegend";
import EmptyState from "../common/EmptyState";
import "./AgentRelationshipGraph.css";

// Tells React Flow "when a node's type is 'agent', render it with our
// AgentNode component instead of the default box." Defined outside the
// component so it's not recreated every render (React Flow warns if it is).
const nodeTypes = { agent: AgentNode };

/**
 * Arranges agents in a simple hub-and-spoke layout: the orchestrator in
 * the center, everyone else in a ring around it. This is a small,
 * readable stand-in for a real force-directed layout — swap for a
 * library like `dagre` or `elkjs` later if the graph grows past ~10 agents.
 */
function layoutNodes(agents) {
  const centerAgent = agents.find((a) => a.role === "orchestrator");
  const ringAgents = agents.filter((a) => a.role !== "orchestrator");

  const centerX = 320;
  const centerY = 220;
  const radius = 190;

  const nodes = [];

  if (centerAgent) {
    nodes.push({
      id: centerAgent.id,
      type: "agent",
      position: { x: centerX - 32, y: centerY - 32 },
      data: { label: centerAgent.name, status: centerAgent.status, color: centerAgent.color },
    });
  }

  ringAgents.forEach((agent, i) => {
    const angle = (i / ringAgents.length) * 2 * Math.PI - Math.PI / 2;
    const x = centerX + radius * Math.cos(angle) - 32;
    const y = centerY + radius * Math.sin(angle) - 32;
    nodes.push({
      id: agent.id,
      type: "agent",
      position: { x, y },
      data: { label: agent.name, status: agent.status, color: agent.color },
    });
  });

  return nodes;
}

function buildEdges(relationships, agentsById) {
  return relationships.map((rel, i) => {
    const sourceColor = agentsById[rel.sourceAgentId]?.color ?? "#64748b";

    return {
      id: `e-${i}`,
      source: rel.sourceAgentId,
      target: rel.targetAgentId,
      animated: rel.active,
      style: {
        stroke: rel.active ? sourceColor : "var(--border-strong)",
        strokeWidth: rel.active ? 2 : 1.5,
        strokeDasharray: rel.type === "data_flow" ? "4 4" : undefined,
      },
      markerEnd: { type: MarkerType.ArrowClosed, color: rel.active ? sourceColor : "#475569" },
    };
  });
}

/**
 * AgentRelationshipGraph — live node/edge diagram showing which agents
 * are connected and which connections are currently active.
 *
 * Props:
 *  - agents: Agent[]  (see services/mockData.js for shape)
 *  - relationships: AgentRelationship[]
 */
export default function AgentRelationshipGraph({ agents, relationships }) {
  const agentsById = useMemo(
    () => Object.fromEntries(agents.map((a) => [a.id, a])),
    [agents]
  );

  const nodes = useMemo(() => layoutNodes(agents), [agents]);
  const edges = useMemo(
    () => buildEdges(relationships, agentsById),
    [relationships, agentsById]
  );

  if (agents.length === 0) {
    return (
      <EmptyState
        icon={Network}
        title="No agents connected"
        description="Connect the backend and start the orchestrator to see agents and their relationships here."
      />
    );
  }

  return (
    <div className="agent-graph-wrapper">
      <div className="agent-graph-canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          nodesDraggable
          nodesConnectable={false}
          elementsSelectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#1f2937" gap={20} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <GraphLegend />
    </div>
  );
}
