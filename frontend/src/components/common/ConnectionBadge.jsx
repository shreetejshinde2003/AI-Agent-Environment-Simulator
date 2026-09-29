import Badge from "./Badge";

/**
 * ConnectionBadge — replaces every hardcoded "Live" pulse badge that
 * used to sit on dashboard cards regardless of whether anything was
 * actually connected. Now it reflects the REAL connectionStatus from
 * useSimulationData()/useBackendConnection().
 *
 * Props:
 *  - connectionStatus: "connecting" | "connected" | "disconnected"
 *  - isDemoMode: boolean — if true, always shows "Demo Mode" so sample
 *    data is never mistaken for a live feed
 *  - compact: boolean — true = short labels for card headers ("Live" /
 *    "Offline"), false = full labels for the Topbar ("Connected" /
 *    "Disconnected")
 */
export default function ConnectionBadge({ connectionStatus, isDemoMode, compact = false }) {
  if (isDemoMode) {
    return <Badge tone="warning">Demo Mode</Badge>;
  }

  if (connectionStatus === "connected") {
    return <Badge tone="success">{compact ? "Live" : "Connected"}</Badge>;
  }

  if (connectionStatus === "connecting") {
    return <Badge tone="warning" pulse>Connecting</Badge>;
  }

  return <Badge tone="neutral">{compact ? "Offline" : "Disconnected"}</Badge>;
}
