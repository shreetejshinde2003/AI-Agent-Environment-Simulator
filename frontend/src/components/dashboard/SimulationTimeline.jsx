import { useState } from "react";
import { Play, Pause, GanttChartSquare } from "lucide-react";
import EmptyState from "../common/EmptyState";
import { colorForRole } from "../../utils/colors";
import "./SimulationTimeline.css";

// USER-DEFINED: playback speed options shown in the footer buttons.
const SPEED_OPTIONS = [0.5, 1, 1.5, 2];

/**
 * SimulationTimeline — per-agent horizontal activity bars + a scrubber,
 * matching the reference image's timeline at the bottom of the dashboard.
 *
 * Props:
 *  - timeline: { [agentName]: [startSec, endSec][] }  (see mockData.mockTimeline)
 *  - totalDurationSeconds: number — right edge of the timeline
 */
export default function SimulationTimeline({ timeline, totalDurationSeconds = 30 }) {
  const [speed, setSpeed] = useState(1);
  const [isPlaying, setIsPlaying] = useState(false);
  // RESERVED: cursorSeconds should be driven by an actual playback
  // interval (setInterval/requestAnimationFrame) once this is wired to
  // real replay data. For now it's just a static example position.
  const [cursorSeconds] = useState(totalDurationSeconds * 0.55);

  const agentNames = Object.keys(timeline);

  if (agentNames.length === 0) {
    return (
      <EmptyState
        icon={GanttChartSquare}
        title="No timeline data available"
        description="RESERVED: the backend doesn't expose per-agent timing data yet — this needs a new endpoint before this chart can show real data."
      />
    );
  }

  const cursorPercent = (cursorSeconds / totalDurationSeconds) * 100;

  return (
    <div className="timeline">
      <div className="timeline-track-area">
        {/* Scrubber cursor line */}
        <div className="timeline-cursor" style={{ left: `${cursorPercent}%` }} />

        {agentNames.map((name) => {
          const roleKey = name.toLowerCase().replace(/\s+agent$/, "").replace(/\s+/g, "_");
          const color = colorForRole(roleKey === "orchestrator" ? "orchestrator" : roleKey);

          return (
            <div key={name} className="timeline-row">
              <span className="timeline-row-label">{name}</span>
              <div className="timeline-row-track">
                {timeline[name].map(([start, end], i) => (
                  <div
                    key={i}
                    className="timeline-segment"
                    style={{
                      left: `${(start / totalDurationSeconds) * 100}%`,
                      width: `${((end - start) / totalDurationSeconds) * 100}%`,
                      background: color,
                    }}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <div className="timeline-footer">
        <button
          type="button"
          className="timeline-play-btn"
          onClick={() => setIsPlaying((p) => !p)}
          aria-label={isPlaying ? "Pause" : "Play"}
        >
          {isPlaying ? <Pause size={14} /> : <Play size={14} />}
        </button>

        <div className="timeline-speed-group">
          {SPEED_OPTIONS.map((s) => (
            <button
              key={s}
              type="button"
              className={`timeline-speed-btn${s === speed ? " is-active" : ""}`}
              onClick={() => setSpeed(s)}
            >
              {s}x
            </button>
          ))}
        </div>

        <button type="button" className="timeline-go-live-btn">
          Go to Live
        </button>
      </div>
    </div>
  );
}
