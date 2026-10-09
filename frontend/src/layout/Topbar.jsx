import {Target, RotateCcw} from "lucide-react";
import Badge from "../components/common/Badge";
import {readiness} from "../utils/readiness";
import "./Topbar.css";
export default function Topbar({goal, backendStatus, workspaceStatus, socketStatus, onToggleReplay, dataStatus = "ready", isRefreshing = false, lastRefreshedAt, onRefresh, authError}) {
  const state = readiness({backendStatus, workspaceStatus, dataStatus, isRefreshing, authError});
  return <header className="topbar">
    {goal && <div className="topbar-goal"><div className="topbar-goal-icon"><Target size={18}/></div>
      <div className="topbar-goal-text"><span className="topbar-goal-label">Selected task</span><span className="topbar-goal-value" title={goal}>{goal}</span></div></div>}
    <div className="topbar-actions">
      <details className="readiness-details"><summary aria-label={`System status: ${state.label}`}><Badge tone={state.tone}>{state.label}</Badge></summary>
        <div className="readiness-panel"><p>{state.message}</p>
          <p>Last successful update: {lastRefreshedAt ? new Date(lastRefreshedAt).toLocaleTimeString() : "Waiting for saved records"}.</p>
          {onRefresh && <button className="topbar-btn" disabled={isRefreshing} onClick={onRefresh}>{isRefreshing ? "Updating…" : "Refresh saved results"}</button>}
          <details><summary>Connection details</summary>
            <p>{backendStatus === "connected" ? "Backend reachable" : "Backend unavailable"} · {workspaceStatus === "ready" ? "Workspace ready" : workspaceStatus === "error" ? "Workspace unavailable" : "Workspace access is being checked"}.</p>
            <p>{socketStatus === "connected" ? "Instant updates connected. Automatic refresh is also available." : socketStatus === "disabled" ? "Automatic refresh is the configured update method. Instant updates are not enabled." : "Automatic refresh is used when an instant connection is unavailable."}</p>
          </details>
        </div>
      </details>
      {onToggleReplay && <button className="topbar-btn" onClick={onToggleReplay}><RotateCcw size={15}/> Execution events</button>}
    </div>
  </header>;
}
