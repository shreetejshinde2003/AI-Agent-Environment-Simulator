import { Bot, ListChecks, MessagesSquare, Timer, TrendingUp } from "lucide-react";
import StatsCard from "./StatsCard";
import { formatSeconds } from "../../utils/formatTime";

/**
 * StatsCardRow — the 5-card row at the top of the Live Simulation page:
 * Agents Active, Tasks Completed, Messages, Avg. Response Time, Success Rate.
 *
 * IMPORTANT: these values come straight from useSimulation().stats,
 * which is a genuine zero/offline state whenever there's no backend
 * connection or no real agents running (see hooks/useSimulationData.js).
 * This component must never invent numbers — if you're tempted to add
 * a fallback/placeholder value here, don't; show the real zero instead.
 */
export default function StatsCardRow({ stats }) {
  // Rate-based metrics (avg response time, success rate) are only
  // meaningful once at least one task has actually run — showing
  // "0.00s" or "0%" before anything has happened reads as "the system
  // is fast/perfect" rather than "nothing has happened yet". Count-based
  // metrics (agents, tasks, messages) show a real 0 as-is, per the
  // team's call: no fabricated data, ever, but a literal 0 is honest
  // for a count.
  const hasRunAnything = stats.totalTasks > 0;

  const cards = [
    {
      icon: Bot,
      iconColor: "#22c55e",
      label: "Agents Active",
      value: `${stats.activeAgents} / ${stats.totalAgents}`,
    },
    {
      icon: ListChecks,
      iconColor: "#3b82f6",
      label: "Tasks Completed",
      value: `${stats.completedTasks} / ${stats.totalTasks}`,
    },
    {
      icon: MessagesSquare,
      iconColor: "#8b5cf6",
      label: "Messages",
      value: stats.totalMessages,
    },
    {
      icon: Timer,
      iconColor: "#f59e0b",
      label: "Avg. Response Time",
      value: hasRunAnything ? formatSeconds(stats.avgResponseTimeSeconds) : "—",
    },
    {
      icon: TrendingUp,
      iconColor: "#22c55e",
      label: "Success Rate",
      value: hasRunAnything ? `${stats.successRatePercent}%` : "—",
    },
  ];

  return (
    <div className="stats-card-row">
      {cards.map((card) => (
        <StatsCard key={card.label} {...card} />
      ))}
    </div>
  );
}
