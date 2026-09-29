import { useMemo } from "react";
import ReactFlow, { Background, Controls, Handle, Position } from "reactflow";
import "reactflow/dist/style.css";
import "./AgentRelationshipGraph.css";
import { graphPath } from "../../utils/runs";
import { edgeView, stageView } from "../../utils/graphPresentation";
import { graphTarget } from "../../utils/workspaceSelection";
function StageNode({data}) {
  return <button type="button" onClick={data.onInspect}
    className={"pipeline-node state-" + data.status + (data.selected ? " is-selected" : "")}
    aria-pressed={data.selected} aria-label={`${data.label}, ${data.statusText}, ${data.kind}`}>
    <Handle type="target" position={Position.Top} isConnectable={false} aria-hidden="true"/>
    <span className="node-kind">{data.kind}</span><strong>{data.label}</strong>
    <span className="node-status">{data.statusText}</span>
    <Handle type="source" position={Position.Bottom} isConnectable={false} aria-hidden="true"/>
  </button>;
}
const NODE_TYPES = {stage: StageNode};
export default function AgentRelationshipGraph({task, agents = [], selectedTarget = null, onInspect = () => {}}) {
  const {nodes, edges} = useMemo(() => {
    const stageMap = Object.fromEntries((task?.stages ?? []).map(s => [s.agentId, s]));
    const running = task?.status === "in_progress";
    const orchestration = running ? "active" : task?.status === "completed" ? "completed" :
      task?.status === "failed" ? "failed" : "waiting";
    const ids = graphPath(task);
    const nodes = ids.map((id, i) => {
      const view = stageMap[id] ? stageView(task, stageMap[id]) :
        id === "goal" ? {status: task ? "completed" : "waiting", text: task ? "Goal received" : "Waiting"} :
        id === "result" ? task?.status === "completed" ? {status: "completed", text: "Completed"} :
          task?.status === "failed" ? {status: "not-executed", text: "No final result"} :
          {status: "waiting", text: "Waiting"} :
        {status: orchestration, text: orchestration === "active" ? "Coordinating" : orchestration};
      return {
      id, type: "stage", position: {x: 120, y: i * 122},
      data: {label: id === "goal" ? "User Goal" : id === "result" ? "Final Result" :
        agents.find(a => a.id === id)?.name ?? id,
        onInspect: () => onInspect(graphTarget(id)),
        kind: id === "orchestrator" ? "Sequential coordinator · no LLM" :
          ["goal", "result"].includes(id) ? "Simulation" : "Agent",
        status: view.status, statusText: view.text,
        selected: selectedTarget?.kind === "stage" ? selectedTarget.id === id : selectedTarget?.kind === id},
      };
    });
    const edges = ids.slice(0, -1).map((id, i) => {
      const next = ids[i+1];
      const handoff = task?.messages?.find(m => m.fromAgentId === id && m.toAgentId === next);
      const view = task ? edgeView(task, id, next, stageMap, handoff) : {recorded: false, animated: false, label: ""};
      return {id: id + "-" + next, source: id, target: next,
        label: view.label, animated: view.animated,
        style: {stroke: view.recorded ? "#22c55e" : "#475569", strokeWidth: view.recorded ? 2 : 1},
        labelStyle: {fill: "#cbd5e1", fontSize: 11}, labelBgStyle: {fill: "#111827"},
        data: {message: handoff}};
    });
    return {nodes, edges};
  }, [task, agents, selectedTarget, onInspect]);
  if (!task) return <p className="empty-note">No run selected. Create or choose a simulation to see its recorded execution path.</p>;
  return <div>
    <p className="muted">Select a node or a recorded handoff to inspect execution details. Web Search is unavailable.</p>
    <div className="pipeline-graph" role="group" aria-label="Simulation pipeline graph">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} fitView
        fitViewOptions={{padding: 0.12}} minZoom={0.3} maxZoom={1.3}
        nodesDraggable={false} nodesConnectable={false} nodesFocusable={false} edgesFocusable={false}
        onNodeClick={(_, node) => onInspect(graphTarget(node.id))}
        onEdgeClick={(_, edge) => { if (edge.data?.message?.id) onInspect({kind: "handoff", id: edge.data.message.id}); }}>
        <Background color="#253047" gap={20}/><Controls showInteractive={false}/>
      </ReactFlow>
    </div>
    <div className="graph-key"><span>○ Selected · waiting</span><span className="active">● Running</span>
      <span className="completed">✓ Completed</span><span className="failed">✕ Failed</span>
      <span>— Not executed</span></div>
    {!!task.messages?.length && <div className="graph-handoffs" aria-label="Recorded handoffs">
      <strong>Recorded handoffs</strong>
      {task.messages.map(handoff => <button type="button" className="text-button" key={handoff.id}
        onClick={() => onInspect({kind: "handoff", id: handoff.id})}
        aria-pressed={selectedTarget?.kind === "handoff" && selectedTarget.id === handoff.id}
        aria-label={`Inspect ${handoff.fromAgentId} to ${handoff.toAgentId} handoff, ${handoff.outputKey}`}>
        {handoff.fromAgentId} → {handoff.toAgentId} · {handoff.outputKey}
      </button>)}
    </div>}
  </div>;
}
