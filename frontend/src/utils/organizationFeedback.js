// Do not disclose whether a private organization or particular secret exists.
export function organizationFeedback(error, action) {
  if (error.outcomeUnknown) return "The server did not confirm the result. Reload your workspaces or invitation history before trying again; the action may already have saved.";
  if (error.status === 401) return "Your session changed or expired. Recheck sign-in before continuing.";
  if (error.status === 403) return "Your current role cannot do this. Ask an organization Owner or Admin for help.";
  if (action === "join" && [400,404,409].includes(error.status)) return "This invitation cannot be used. It may be incorrect, already used, or revoked. Ask an Owner or Admin for a new code.";
  if (error.status === 409) return "This information changed while you were working. Reload before trying again.";
  if (error.status == null || error.status >= 500) return "We could not confirm this action. Check your connection and reload before retrying.";
  return "The action could not be completed. Check the details and try again.";
}
