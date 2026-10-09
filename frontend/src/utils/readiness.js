export function readiness({backendStatus, workspaceStatus, dataStatus = "ready", authError, isRefreshing}) {
  if (authError) return {label: "Sign in again", tone: "warning", message: "Your sign-in changed or expired. Recheck your session before continuing."};
  if (dataStatus === "error" || workspaceStatus === "error" || ["error", "disconnected"].includes(backendStatus))
    return {label: "Connection problem", tone: "warning", message: "Saved records could not be refreshed. Your last loaded results may be out of date. Try refreshing."};
  if (backendStatus !== "connected" || workspaceStatus !== "ready" || dataStatus === "loading")
    return {label: "Updating", tone: "neutral", message: "Preparing your connection and loading saved work."};
  return {label: "Ready", tone: "success", message: isRefreshing ? "Checking for saved updates… You can continue working." : "Your workspace is ready. Saved results refresh automatically every five seconds."};
}
