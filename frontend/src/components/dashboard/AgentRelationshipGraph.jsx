import { useMemo, useState } from "react";
import ReactFlow, { Background, Controls, Handle, Position } from "reactflow";
import "reactflow/dist/style.css";
import "./AgentRelationshipGraph.css";
const ORDER = ["research", "data", "analysis", "summarizer", "report"];
function StageNode({data}) {
  return <button type="button" onClick={data.onInspect} className={"pipeline-node state-" + data.status}>
    <Handle type="target" position={Position.Top}/>
    <span className="node-kind">{data.kind}</span><strong>{data.label}</strong>
    <span className="node-status">{data.status.toUpperCase()}</span>
    <Handle type="source" position={Position.Bottom}/>
  </button>;
}
const NODE_TYPES = {stage: StageNode};
export default function AgentRelationshipGraph({task, agents = []}) {
  const [inspectId, setInspectId] = useState(null);
  const {nodes, edges} = useMemo(() => {
    const sequence = task?.stages?.map(s => s.agentId) ?? ORDER;
    const stageMap = Object.fromEntries((task?.stages ?? []).map(s => [s.agentId, s]));
    const running = task?.status === "in_progress";
    const orchestration = running ? "active" : task?.status === "completed" ? "completed" :
      task?.status === "failed" ? "failed" : "waiting";
    const isFixed = !task || ["fixed", "full_pipeline"].includes(task.executionMode);
    const ids = ["goal", ...(isFixed ? ["orchestrator"] : []), ...sequence, "result"];
    const nodes = ids.map((id, i) => ({
      id, type: "stage", position: {x: 120, y: i * 122},
      data: {label: id === "goal" ? "User Goal" : id === "result" ? "Final Result" :
        agents.find(a => a.id === id)?.name ?? id,
        onInspect: () => setInspectId(id),
        kind: id === "orchestrator" ? "Sequential coordinator · no LLM" :
          ["goal", "result"].includes(id) ? "Simulation" : "Agent",
        status: stageMap[id]?.status ?? (id === "goal" ? task ? "completed" : "waiting" :
          id === "result" ? task?.status === "completed" ? "completed" : "waiting" :
          id === "orchestrator" ? orchestration : "waiting")},
    }));
    const edges = ids.slice(0, -1).map((id, i) => {
      const next = ids[i+1];
      const handoff = task?.messages?.find(m => m.fromAgentId === id && m.toAgentId === next);
      const actual = handoff || (id === "goal" && task?.executionStartedAt) ||
        (id === "orchestrator" && stageMap[next]?.startedAt) ||
        (id === "goal" && stageMap[next]?.startedAt) ||
        (next === "result" && task?.status === "completed");
      return {id: id + "-" + next, source: id, target: next,
        label: handoff?.outputKey ?? (stageMap[id]?.outputKey || ""),
        animated: !!handoff && stageMap[next]?.status === "active",
        style: {stroke: actual ? "#22c55e" : "#475569", strokeWidth: actual ? 2 : 1},
        labelStyle: {fill: "#cbd5e1", fontSize: 11}, labelBgStyle: {fill: "#111827"},
        data: {message: handoff}};
    });
    return {nodes, edges};
  }, [task, agents]);
  const stage = task?.stages?.find(s => s.agentId === inspectId);
  const message = task?.messages?.find(m => m.id === inspectId);
  return <div>
    <p className="muted">Select a node or handoff to inspect real execution details. Web Search: not implemented.</p>
    <div className="pipeline-graph" aria-label="Simulation pipeline graph">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} fitView
        fitViewOptions={{padding: 0.12}} minZoom={0.3} maxZoom={1.3}
        nodesDraggable={false} nodesConnectable={false} nodesFocusable={false}
        onNodeClick={(_, node) => setInspectId(node.id)}
        onEdgeClick={(_, edge) => setInspectId(edge.data?.message?.id ?? null)}>
        <Background color="#253047" gap={20}/><Controls showInteractive={false}/>
      </ReactFlow>
    </div>
    <div className="graph-key"><span>○ Waiting</span><span className="active">● Active</span>
      <span className="completed">● Completed</span><span className="failed">● Failed</span></div>
    {inspectId && <div className="inspector">
      <button className="text-button" onClick={() => setInspectId(null)}>Close details</button>
      {stage ? <>
        <h3>{stage.agentId} · {stage.status}</h3>
        <p>Model: {stage.model ?? "Not recorded"} · Tokens: {stage.totalTokens ?? "Not recorded"} ·
          Response time: {stage.durationSeconds == null ? "Not recorded" : stage.durationSeconds.toFixed(2) + "s"}</p>
        <p>Executions in this run: {stage.startedAt ? 1 : 0}</p>
        <p>Latest activity: {task.activities?.filter(a => a.agentId === stage.agentId).at(-1)?.text ?? "No activity yet"}</p>
        {stage.error && <p className="run-error">{stage.error}</p>}
        <details><summary>Stage output ({stage.output?.length ?? 0} characters)</summary><pre>{stage.output || "No output yet"}</pre></details>
      </> : message ? <>
        <h3>{message.fromAgentId} → {message.toAgentId}</h3>
        <p>{message.outputKey} · {message.kind} · {new Date(message.timestamp).toLocaleString()}</p>
        <pre>{message.content}</pre>
      </> : <p>{inspectId === "orchestrator" ? "The existing sequential coordinator runs each stage in order and stops on failure. It is not an LLM agent." :
        inspectId === "result" ? task?.output ?? "No final result yet" : task?.directive ?? "No simulation selected"}</p>}
    </div>}
  </div>;
}
