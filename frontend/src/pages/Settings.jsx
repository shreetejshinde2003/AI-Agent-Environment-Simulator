import { API_BASE_URL, WS_URL } from "../services/apiClient";
import Card from "../components/common/Card";
export default function Settings() {
  return <div className="workspace-stack"><h1>Workspace settings</h1>
    <Card title="Connection configuration"><p>Connection settings are configured at deployment, not through cosmetic local switches.</p>
      <dl className="metadata"><dt>API origin</dt><dd>{API_BASE_URL}</dd><dt>Live events</dt><dd>{WS_URL}</dd></dl></Card>
    <Card title="Authentication"><p>Google OAuth/OpenID Connect is enabled for user authentication. The backend creates a local user identity and a revocable application session.</p>
      <p>Organization membership, role-based access control and tenant isolation are enforced. HR roles are separate from workspace administration.</p></Card>
    <Card title="Supported behavior"><p>Single uses one Direct Agent. Fixed runs five specialists in order. Adaptive selects specialists with deterministic rules. Individual Specialist is a separate utility mode.</p>
      <p>Web Search, active-request pause/cancellation, retries and PDF ingestion are unavailable. Custom text agents are supported. Production graph execution remains disabled.</p>
      <p>Local development uses SQLite by default. Production uses Railway PostgreSQL, and simulation history has been verified across a backend restart. Benchmark JSON files require separate private provisioning.</p></Card>
  </div>;
}
