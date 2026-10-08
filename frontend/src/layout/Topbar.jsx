import { Target, RotateCcw } from "lucide-react";
import Badge from "../components/common/Badge";
import "./Topbar.css";
export default function Topbar({goal, backendStatus, workspaceStatus, socketStatus, onToggleReplay}) {
  return <header className="topbar">
    {goal && <div className="topbar-goal">
      <div className="topbar-goal-icon"><Target size={18}/></div>
      <div className="topbar-goal-text"><span className="topbar-goal-label">Selected Goal</span>
        <span className="topbar-goal-value" title={goal}>{goal}</span></div>
    </div>}
    <div className="topbar-actions">
      <details className="readiness-details"><summary><Badge tone={backendStatus === "connected" && workspaceStatus === "ready" ? (socketStatus === "connected" ? "success" : "neutral") : "warning"}>
        {backendStatus === "connected" ? workspaceStatus === "ready" ? socketStatus === "connected" ? "Ready" : "Limited connectivity" : workspaceStatus === "error" ? "Workspace unavailable" : "Preparing workspace" : backendStatus === "connecting" ? "Checking connection" : "Offline"}
      </Badge></summary>
      <div className="readiness-panel"><p>{backendStatus === "connected" && workspaceStatus === "ready" && socketStatus !== "connected" ? "You can use the app. Live updates are unavailable; saved runs refresh automatically." : "Workspace actions require an available backend and workspace."}</p>
      <Badge tone={backendStatus === "connected" ? "success" : "warning"}>
        {backendStatus === "connected" ? "Backend reachable" : backendStatus === "connecting" ? "Checking backend" : "Backend unavailable"}
      </Badge>
      <Badge tone={workspaceStatus === "ready" ? "success" : "warning"}>
        {workspaceStatus === "ready" ? "Workspace ready" : workspaceStatus === "error" ? "Workspace unavailable" : "Loading workspace"}
      </Badge>
      <Badge tone={socketStatus === "connected" ? "success" : "neutral"}>
        {socketStatus === "connected" ? "Live events connected" : "Live events offline"}
      </Badge>
      </div></details>
      {onToggleReplay && <button className="topbar-btn" onClick={onToggleReplay}><RotateCcw size={15}/> Execution events</button>}
    </div>
  </header>;
}
