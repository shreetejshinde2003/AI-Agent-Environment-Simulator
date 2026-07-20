import { useSimulation } from "../context/SimulationContext";
import StatsCardRow from "../components/dashboard/StatsCardRow";
import AgentRelationshipGraph from "../components/dashboard/AgentRelationshipGraph";
import TaskDetailsPanel from "../components/dashboard/TaskDetailsPanel";
import MessageFlowFeed from "../components/dashboard/MessageFlowFeed";
import SimulationTimeline from "../components/dashboard/SimulationTimeline";
import ActivityFeed from "../components/dashboard/ActivityFeed";
import QuickActions from "../components/dashboard/QuickActions";
import Card from "../components/common/Card";
import ConnectionBadge from "../components/common/ConnectionBadge";
import "./LiveSimulation.css";

/**
 * LiveSimulation — the main dashboard page (the reference image).
 * Pulls everything from useSimulation() and lays out the cards in a
 * 3-column grid: graph+messages (left, wide), task details+activity
 * (right, narrow).
 *
 * Every card's "Live" badge now comes from ConnectionBadge, which
 * reflects the REAL connection status — it does not say "Live" just
 * because the component rendered. See hooks/useSimulationData.js and
 * hooks/useBackendConnection.js for where that status actually comes from.
 */
export default function LiveSimulation() {
  const {
    agents,
    relationships,
    messages,
    activity,
    stats,
    timeline,
    selectedTask,
    connectionStatus,
    isDemoMode,
  } = useSimulation();

  return (
    <div className="live-sim-page">
      {isDemoMode && (
        <div className="demo-mode-banner">
          <strong>Demo Mode</strong> — showing sample data. This is NOT connected to a
          live backend. Remove <code>?demo=true</code> or unset <code>VITE_DEMO_MODE</code>
          to see real (currently empty) data.
        </div>
      )}

      {!isDemoMode && connectionStatus === "disconnected" && (
        <div className="offline-banner">
          Backend not reachable — all values below are genuine zeros, not sample data.
          Start the backend (see <code>/backend/README.md</code>) to see live data.
        </div>
      )}

      <StatsCardRow stats={stats} />

      <div className="live-sim-grid">
        {/* --- Left column: graph + message flow + timeline --- */}
        <div className="live-sim-col-main">
          <Card
            title="Agent Relationship Graph"
            headerRight={<ConnectionBadge connectionStatus={connectionStatus} isDemoMode={isDemoMode} compact />}
          >
            <AgentRelationshipGraph agents={agents} relationships={relationships} />
          </Card>

          <div className="live-sim-row-split">
            <Card
              title="Message Flow"
              headerRight={<ConnectionBadge connectionStatus={connectionStatus} isDemoMode={isDemoMode} compact />}
            >
              <MessageFlowFeed messages={messages} agents={agents} />
            </Card>

            <Card
              title="Simulation Timeline"
              headerRight={<ConnectionBadge connectionStatus={connectionStatus} isDemoMode={isDemoMode} compact />}
            >
              <SimulationTimeline timeline={timeline} totalDurationSeconds={30} />
            </Card>
          </div>
        </div>

        {/* --- Right column: task details + activity + quick actions --- */}
        <div className="live-sim-col-side">
          <Card
            title="Task Details"
            headerRight={<ConnectionBadge connectionStatus={connectionStatus} isDemoMode={isDemoMode} compact />}
          >
            <TaskDetailsPanel task={selectedTask} agents={agents} />
          </Card>

          <Card
            title="Activity Feed"
            headerRight={<ConnectionBadge connectionStatus={connectionStatus} isDemoMode={isDemoMode} compact />}
          >
            <ActivityFeed activity={activity} agents={agents} />
          </Card>

          <Card title="Quick Actions">
            <QuickActions />
          </Card>
        </div>
      </div>
    </div>
  );
}
