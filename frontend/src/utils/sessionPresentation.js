// Fixed copy deliberately excludes server messages, OAuth details and response bodies.
export function sessionPresentation(error, context = "session") {
  if (error?.code === "session_expired") return {title: "Session expired", message: "Your session has expired. Sign in again to continue.", signIn: true};
  if (error?.code === "unexpected_api_response" && !(error?.status >= 500)) return {title: "Unable to connect", message: "The application received an unexpected response. Try again in a moment."};
  if (error?.status === 401) return {title: "Sign in again", message: "Your session is no longer available. Sign in again to continue.", signIn: true};
  if (error?.status === 403) return {title: "Access unavailable", message: "This account cannot access the application. Try another account or contact your workspace administrator.", signIn: true};
  if (error?.status >= 500) return {title: "Server unavailable", message: "The server is temporarily unavailable. Try again in a moment."};
  if (error?.name === "TimeoutError") return {title: "Connection timed out", message: "The server took too long to respond. Check your connection and try again."};
  if (error?.status == null && error) return {title: "Connection interrupted", message: "We could not reach the application. Check your connection and try again."};
  return {title: context === "workspace" ? "Workspace unavailable" : "Sign-in check failed", message: context === "workspace" ? "We could not load your workspaces. Try again." : "We could not verify your sign-in. Try again or sign in with Google."};
}
