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
      <Badge tone={backendStatus === "connected" ? "success" : "warning"}>
        {backendStatus === "connected" ? "Backend reachable" : backendStatus === "connecting" ? "Checking backend" : "Backend unavailable"}
      </Badge>
      <Badge tone={workspaceStatus === "ready" ? "success" : "warning"}>
        {workspaceStatus === "ready" ? "Workspace ready" : workspaceStatus === "error" ? "Workspace unavailable" : "Loading workspace"}
      </Badge>
      <Badge tone={socketStatus === "connected" ? "success" : "neutral"}>
        {socketStatus === "connected" ? "Live events connected" : "Live events offline"}
      </Badge>
      {onToggleReplay && <button className="topbar-btn" onClick={onToggleReplay}><RotateCcw size={15}/> Execution events</button>}
    </div>
  </header>;
}
