import { API_BASE_URL, WS_URL } from "../services/apiClient";
import Card from "../components/common/Card";
export default function Settings() {
  return <div className="workspace-stack"><h1>Workspace settings</h1>
    <Card title="Connection configuration"><p>Connection settings are configured at deployment, not through cosmetic local switches.</p>
      <dl className="metadata"><dt>API origin</dt><dd>{API_BASE_URL}</dd><dt>Live events</dt><dd>{WS_URL}</dd></dl></Card>
    <Card title="Shared workspace · V1"><p>There is no login or private ownership enforcement. Runs have an optional owner field reserved for future authentication.</p>
      <p>Do not upload private data. All users of this backend can read its simulations, uploads, messages, and exports.</p></Card>
    <Card title="Supported behavior"><p>Five real agents run sequentially or individually. Web Search, active-request pause/cancellation,
      custom executable agents, PDF ingestion, and authentication are not implemented.</p>
      <p>SQLite history survives application restarts on the same disk. Production deployments need durable storage before relying on history.</p></Card>
  </div>;
}
