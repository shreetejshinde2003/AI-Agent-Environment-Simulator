import { apiError } from "../utils/apiErrors";

function responseError(message, response, requestPath) {
  const error = new Error(message);
  error.status = response.status;
  error.code = "unexpected_api_response";
  // Only caller-supplied path, without query/fragment, and bounded metadata.
  error.requestPath = requestPath.split(/[?#]/, 1)[0];
  error.contentType = (response.headers.get("content-type") || "missing").slice(0, 100);
  return error;
}

export function requireResponseType(response, requestPath, expectedType) {
  const contentType = response.headers.get("content-type") || "";
  const mediaType = contentType.split(";", 1)[0].trim().toLowerCase();
  const matches = expectedType === "application/json"
    ? /^application\/(?:json|[a-z0-9!#$&^_.+-]+\+json)$/.test(mediaType)
    : mediaType === expectedType;
  if (!matches) {
    throw responseError(expectedType === "application/json"
      ? "API returned an unexpected non-JSON response."
      : "API returned an unexpected response type.", response, requestPath);
  }
}

export async function parseApiResponse(response, requestPath) {
  requireResponseType(response, requestPath, "application/json");
  let payload;
  try { payload = await response.json(); }
  catch { throw responseError("API returned an invalid JSON response.", response, requestPath); }
  if (!response.ok) {
    const error = apiError(payload?.detail, response.status);
    // A real API 401 ends the local authenticated view; no redirect loop or retry
    // of mutations. HTML/proxy errors above never masquerade as session expiry.
    if (response.status === 401 && typeof window !== "undefined" &&
        !requestPath.startsWith("/api/v1/auth/")) {
      window.dispatchEvent(new CustomEvent("session-unavailable", {detail: error}));
    }
    throw error;
  }
  return payload;
}
