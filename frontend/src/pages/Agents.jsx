import { useSimulation } from "../context/SimulationContext";
import AgentBuilder from "../components/dashboard/AgentBuilder";
import {useWorkspace} from "../hooks/useWorkspace";
import Card from "../components/common/Card";
export default function Agents() {
  const {activeWorkspaceId, activeWorkspace} = useWorkspace();
  const {agents, metrics, acceptRun, selectTask, refresh} = useSimulation();
  return <div className="workspace-stack"><h1>Agent directory</h1>
    <p className="muted">Five specialist agents and one Direct baseline agent are executable. The coordinator makes no model call. Status is across the shared workspace; metrics come from saved stage attempts.</p>
    <AgentBuilder key={activeWorkspaceId} workspaceId={activeWorkspaceId} workspace={activeWorkspace}
      onRunCreated={run => {acceptRun(run); selectTask(run.id); refresh();}} />
    <h2>System agent directory</h2><p className="muted">Built-in agents are protected and cannot be archived or deleted.</p>
    <div className="run-grid equal">{agents.map(agent => {
      const stats = metrics.agents.find(a => a.agentId === agent.id);
      return <Card key={agent.id} title={agent.name}>
        <p>{agent.id === "orchestrator" ? "Coordinates the pipeline · no LLM call" :
          !agent.implemented ? "Not implemented · unavailable for execution" : agent.status}</p>
        {stats && <dl className="metadata">
          <dt>Stage attempts / completed / failed</dt><dd>{stats.calls} / {stats.completed} / {stats.failed}</dd>
          <dt>Model</dt><dd>{stats.lastExecution?.model ?? "No model recorded yet"}</dd>
          <dt>Total / average tokens</dt><dd>{stats.measuredCalls ? stats.totalTokens + " / " + stats.averageTokens.toFixed(1) : "Not recorded"}</dd>
          <dt>Average response</dt><dd>{stats.averageLatency == null ? "Not recorded" : stats.averageLatency.toFixed(2) + "s"}</dd>
          <dt>Last execution</dt><dd>{stats.lastExecution ? new Date(stats.lastExecution.startedAt).toLocaleString() : "Never"}</dd>
        </dl>}
      </Card>;
    })}</div></div>;
}
