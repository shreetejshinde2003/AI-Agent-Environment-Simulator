import { useSimulation } from "../context/SimulationContext";
import Card from "../components/common/Card";
export default function Agents() {
  const {agents, metrics} = useSimulation();
  return <div className="workspace-stack"><h1>Agent directory</h1>
    <p className="muted">Five executable agents, one sequential coordinator. Metrics come from saved stage executions.</p>
    <div className="run-grid equal">{agents.map(agent => {
      const stats = metrics.agents.find(a => a.agentId === agent.id);
      return <Card key={agent.id} title={agent.name}>
        <p>{agent.id === "orchestrator" ? "Coordinates the pipeline · no LLM call" :
          !agent.implemented ? "Not implemented · unavailable for execution" : agent.status}</p>
        {stats && <dl className="metadata">
          <dt>Calls / success / failed</dt><dd>{stats.calls} / {stats.completed} / {stats.failed}</dd>
          <dt>Model</dt><dd>{stats.lastExecution?.model ?? "No model recorded yet"}</dd>
          <dt>Total / average tokens</dt><dd>{stats.measuredCalls ? stats.totalTokens + " / " + stats.averageTokens.toFixed(1) : "Not recorded"}</dd>
          <dt>Average response</dt><dd>{stats.averageLatency == null ? "Not recorded" : stats.averageLatency.toFixed(2) + "s"}</dd>
          <dt>Last execution</dt><dd>{stats.lastExecution ? new Date(stats.lastExecution.startedAt).toLocaleString() : "Never"}</dd>
        </dl>}
      </Card>;
    })}</div></div>;
}
