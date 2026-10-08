import Badge from "./Badge";

// REST availability only; live transport and workspace status have separate labels.
export default function ConnectionBadge({ connectionStatus, isDemoMode, compact = false }) {
  if (isDemoMode) {
    return <Badge tone="warning">Demo Mode</Badge>;
  }

  if (connectionStatus === "connected") {
    return <Badge tone="success">{compact ? "REST" : "REST available"}</Badge>;
  }

  if (connectionStatus === "connecting") {
    return <Badge tone="warning" pulse>Connecting</Badge>;
  }

  return <Badge tone="neutral">{compact ? "Offline" : "Disconnected"}</Badge>;
}
