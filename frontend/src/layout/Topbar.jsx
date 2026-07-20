import { Target, RotateCcw, Pause, Play, Square, Bell } from "lucide-react";
import ConnectionBadge from "../components/common/ConnectionBadge";
import "./Topbar.css";

/**
 * Topbar
 * Shows the current simulation goal, real connection status, and
 * playback/notification controls.
 *
 * Playback controls (Replay/Pause/Stop) are disabled unless a real
 * simulation is actually connected and running — there's nothing to
 * pause or stop when the backend isn't reachable, so the buttons say
 * so instead of pretending to work.
 *
 * Props:
 *  - goal: string — current simulation goal, or a status message when
 *    there's no real goal to show (see App.jsx for how this is decided)
 *  - isPaused: boolean
 *  - connectionStatus: "connecting" | "connected" | "disconnected"
 *  - isDemoMode: boolean
 *  - onToggleReplay / onTogglePause / onStop: () => void
 *  - notificationCount: number
 *  - onOpenNotifications: () => void
 */
export default function Topbar({
  goal = "No active goal",
  isPaused = false,
  connectionStatus = "disconnected",
  isDemoMode = false,
  onToggleReplay = () => {},
  onTogglePause = () => {},
  onStop = () => {},
  notificationCount = 0,
  onOpenNotifications = () => {},
}) {
  // Controls only make sense once there's an actual simulation to
  // control — demo mode counts as "controllable" for UI-review purposes.
  const canControlSimulation = isDemoMode || connectionStatus === "connected";

  return (
    <header className="topbar">
      <div className="topbar-goal">
        <div className="topbar-goal-icon">
          <Target size={18} strokeWidth={2} />
        </div>
        <div className="topbar-goal-text">
          <span className="topbar-goal-label">Current Goal</span>
          <span className="topbar-goal-value">{goal}</span>
        </div>
      </div>

      <div className="topbar-actions">
        <ConnectionBadge connectionStatus={connectionStatus} isDemoMode={isDemoMode} />

        <button
          type="button"
          className="topbar-btn"
          onClick={onToggleReplay}
          disabled={!canControlSimulation}
          title={canControlSimulation ? undefined : "No backend connection to replay"}
        >
          <RotateCcw size={15} strokeWidth={2} />
          <span>Replay Mode</span>
        </button>

        <button
          type="button"
          className="topbar-btn"
          onClick={onTogglePause}
          disabled={!canControlSimulation}
          title={canControlSimulation ? undefined : "No running simulation to pause"}
        >
          {isPaused ? <Play size={15} strokeWidth={2} /> : <Pause size={15} strokeWidth={2} />}
          <span>{isPaused ? "Resume" : "Pause"}</span>
        </button>

        <button
          type="button"
          className="topbar-btn topbar-btn-danger"
          onClick={onStop}
          disabled={!canControlSimulation}
          title={canControlSimulation ? undefined : "No running simulation to stop"}
        >
          <Square size={14} strokeWidth={2} />
          <span>Stop Simulation</span>
        </button>

        <button
          type="button"
          className="topbar-icon-btn"
          onClick={onOpenNotifications}
          aria-label={`Notifications${notificationCount ? `, ${notificationCount} unread` : ""}`}
        >
          <Bell size={17} strokeWidth={2} />
          {notificationCount > 0 && (
            <span className="topbar-badge">{notificationCount}</span>
          )}
        </button>
      </div>
    </header>
  );
}
