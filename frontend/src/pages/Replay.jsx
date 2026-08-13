import { useEffect, useMemo, useRef, useState } from "react";
import { useSimulation } from "../context/SimulationContext";
import AgentRelationshipGraph from "../components/dashboard/AgentRelationshipGraph";
import SimulationTimeline from "../components/dashboard/SimulationTimeline";
import Card from "../components/common/Card";
import ConnectionBadge from "../components/common/ConnectionBadge";
import "./Replay.css";

/**
 * Replay — scrubbable replay of a past simulation.
 *
 * Long-term this is driven by LangGraph checkpoints exposed by
 * backend/app/agents/orchestrator.py (one run = one ordered list of
 * state snapshots). That endpoint doesn't exist yet, so today this
 * page replays the CURRENT in-memory session's `timeline` from
 * useSimulation() — scrubbing forward reveals more of it, exactly like
 * a real checkpoint replay would, just sourced from live state instead
 * of a saved run.
 *
 * ONE-LINE TODO: once the backend exposes checkpoints, wire
 * loadReplayRun() below to the real endpoint, e.g.:
 *   const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/replay/${runId}`);
 */

const SPEED_OPTIONS = [1, 2, 4];
const STEP_INTERVAL_MS = 800; // base ms between steps at 1x speed

// Placeholder until backend/app/agents/orchestrator.py exposes
// LangGraph checkpoints for a saved run.
async function loadReplayRun(runId) {
  console.warn(`Replay endpoint not wired yet — requested run "${runId}"`);
  return null;
}

export default function Replay() {
  const {
    agents = [],
    relationships = [],
    timeline = [],
    connectionStatus,
    isDemoMode,
  } = useSimulation();

  const [step, setStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [runIdInput, setRunIdInput] = useState("");
  const intervalRef = useRef(null);

  const maxStep = Math.max(timeline.length - 1, 0);

  // Playback loop
  useEffect(() => {
    if (!isPlaying) {
      clearInterval(intervalRef.current);
      return undefined;
    }
    if (timeline.length === 0) {
      setIsPlaying(false);
      return undefined;
    }
    intervalRef.current = setInterval(() => {
      setStep((s) => {
        if (s >= maxStep) {
          setIsPlaying(false);
          return s;
        }
        return s + 1;
      });
    }, STEP_INTERVAL_MS / speed);
    return () => clearInterval(intervalRef.current);
  }, [isPlaying, speed, maxStep, timeline.length]);

  const playedTimeline = useMemo(() => timeline.slice(0, step + 1), [timeline, step]);

  const currentEntry = timeline[step] ?? null;

  const handleScrub = (e) => {
    setIsPlaying(false);
    setStep(Number(e.target.value));
  };

  const handlePlayPause = () => {
    if (timeline.length === 0) return;
    if (step >= maxStep) setStep(0); // restart if at the end
    setIsPlaying((p) => !p);
  };

  const handleRestart = () => {
    setIsPlaying(false);
    setStep(0);
  };

  const handleLoadRun = async () => {
    if (!runIdInput.trim()) return;
    await loadReplayRun(runIdInput.trim());
    // Backend not wired yet — no-op beyond the console warning above.
  };

  return (
    <div className="replay-page">
      <Card
        title="Replay a Run"
        headerRight={
          <ConnectionBadge connectionStatus={connectionStatus} isDemoMode={isDemoMode} compact />
        }
      >
        <div className="replay-run-loader">
          <input
            type="text"
            className="replay-run-input"
            placeholder="Run ID (backend endpoint not wired yet)…"
            value={runIdInput}
            onChange={(e) => setRunIdInput(e.target.value)}
          />
          <button type="button" className="replay-btn" onClick={handleLoadRun}>
            Load Run
          </button>
        </div>
        <p className="replay-hint">
          Currently replaying the active session's history ({timeline.length} step
          {timeline.length === 1 ? "" : "s"} recorded). Load a saved run here once
          checkpoint storage exists on the backend.
        </p>
      </Card>

      {timeline.length === 0 ? (
        <Card title="Replay">
          <div className="replay-empty">
            No simulation history to replay yet — start a live simulation first.
          </div>
        </Card>
      ) : (
        <>
          <Card title="Playback Controls">
            <div className="replay-controls">
              <button type="button" className="replay-btn" onClick={handleRestart}>
                ⏮ Restart
              </button>
              <button
                type="button"
                className="replay-btn replay-btn-primary"
                onClick={handlePlayPause}
              >
                {isPlaying ? "⏸ Pause" : "▶ Play"}
              </button>
              <input
                type="range"
                className="replay-scrubber"
                min={0}
                max={maxStep}
                value={step}
                onChange={handleScrub}
              />
              <span className="replay-step-count">
                Step {step + 1} / {timeline.length}
              </span>
              <select
                className="replay-speed-select"
                value={speed}
                onChange={(e) => setSpeed(Number(e.target.value))}
              >
                {SPEED_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s}×
                  </option>
                ))}
              </select>
            </div>
            {currentEntry && (
              <div className="replay-current-entry">
                Now showing:{" "}
                {currentEntry.label ??
                  currentEntry.message ??
                  currentEntry.title ??
                  `Step ${step + 1}`}
              </div>
            )}
          </Card>

          <div className="replay-grid">
            <Card title="Agent Relationship Graph (at this step)">
              <AgentRelationshipGraph agents={agents} relationships={relationships} />
            </Card>

            <Card title="Simulation Timeline (up to this step)">
              <SimulationTimeline timeline={playedTimeline} totalDurationSeconds={30} />
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
