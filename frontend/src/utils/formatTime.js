/**
 * utils/formatTime.js
 *
 * Small, dependency-free time formatting helpers. Kept in one place so
 * every card (Activity Feed, Message Flow, Timeline) shows time the
 * same way instead of each component rolling its own.
 */

/** "10:42:15 AM" style clock time, used in Activity Feed / Message Flow. */
export function formatClockTime(isoString) {
  const date = new Date(isoString);
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** "00:12:45" style elapsed duration, used in the sidebar simulation info. */
export function formatDuration(totalSeconds) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);

  const pad = (n) => String(n).padStart(2, "0");

  if (hours > 0) return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
  return `${pad(minutes)}:${pad(seconds)}`;
}

/** "2.34s" style short duration, used for Avg. Response Time stat card. */
export function formatSeconds(seconds, decimals = 2) {
  return `${seconds.toFixed(decimals)}s`;
}

/** Relative "x minutes ago" — not used by default in the mockups, but
 *  handy for the Logs page later. */
export function formatRelativeTime(isoString) {
  const diffMs = Date.now() - new Date(isoString).getTime();
  const diffSec = Math.round(diffMs / 1000);

  if (diffSec < 60) return "just now";
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  return `${diffHr}h ago`;
}
