import { Target, RotateCcw } from "lucide-react";
import ConnectionBadge from "../components/common/ConnectionBadge";
import "./Topbar.css";
export default function Topbar({goal, connectionStatus, onToggleReplay}) {
  return <header className="topbar">
    {goal && <div className="topbar-goal">
      <div className="topbar-goal-icon"><Target size={18}/></div>
      <div className="topbar-goal-text"><span className="topbar-goal-label">Selected Goal</span>
        <span className="topbar-goal-value" title={goal}>{goal}</span></div>
    </div>}
    <div className="topbar-actions">
      <ConnectionBadge connectionStatus={connectionStatus}/>
      <button className="topbar-btn" onClick={onToggleReplay}><RotateCcw size={15}/> Event history</button>
    </div>
  </header>;
}
