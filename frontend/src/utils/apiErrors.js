export function apiError(detail, status) {
  const message = typeof detail === "string" ? detail : detail?.message ||
    (Array.isArray(detail) ? detail.map(item => `${(item.loc ?? []).filter(value => value !== "body").join(".") || "Request"}: ${item.msg ?? "Invalid value"}`).join("; ") : null) || `Request failed (${status})`;
  const error = new Error(message);
  error.status = status;
  error.code = detail?.code;
  return error;
}
export function creationError(error) {
  // A timeout/network error or server failure cannot establish whether creation
  // was acknowledged. Preserve the draft; never automatically resubmit it.
  error.outcomeUnknown = error.code === "unexpected_api_response" || error.status == null || error.status >= 500;
  return error;
}
