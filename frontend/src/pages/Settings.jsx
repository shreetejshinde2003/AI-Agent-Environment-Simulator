import { API_BASE_URL, WS_URL } from "../services/apiClient";
import Card from "../components/common/Card";
export default function Settings() {
  return <div className="workspace-stack"><h1>Workspace settings</h1>
    <Card title="Connection configuration"><p>Connection settings are configured at deployment, not through cosmetic local switches.</p>
      <dl className="metadata"><dt>API origin</dt><dd>{API_BASE_URL}</dd><dt>Live events</dt><dd>{WS_URL}</dd></dl></Card>
    <Card title="Shared workspace · V1"><p>There is no login or private ownership enforcement. Runs have an optional owner field reserved for future authentication.</p>
      <p>Do not upload private data. All users of this backend can read its simulations, uploads, messages, and exports.</p></Card>
    <Card title="Supported behavior"><p>Single uses one Direct Agent. Fixed runs five specialists in order. Adaptive selects specialists with deterministic rules. Individual Specialist is a separate utility mode.</p>
      <p>Web Search, LangGraph execution, active-request pause/cancellation, retries, custom executable agents, PDF ingestion, and authentication are not implemented.</p>
      <p>Local development uses SQLite by default. Production uses Railway PostgreSQL, and simulation history has been verified across a backend restart. Benchmark JSON files require separate private provisioning.</p></Card>
  </div>;
}
