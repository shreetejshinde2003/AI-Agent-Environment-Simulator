import { API_BASE_URL } from "./apiConfig";
import { parseApiResponse } from "./apiResponse";

export const AUTH_LOGIN_URL =
  API_BASE_URL + "/api/v1/auth/google/login";

export async function getCurrentUser() {
  const response = await fetch(
    API_BASE_URL + "/api/v1/auth/me",
    {
      method: "GET",
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
      signal: AbortSignal.timeout(15000),
    },
  );

  let payload;
  try {
    payload = await parseApiResponse(response, "/api/v1/auth/me");
  } catch (error) {
    if (response.status === 401 && error.code !== "unexpected_api_response") return null;
    throw error;
  }

  return payload?.authenticated
    ? payload.user
    : null;
}

export async function logout() {
  const response = await fetch(
    API_BASE_URL + "/api/v1/auth/logout",
    {
      method: "POST",
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
      signal: AbortSignal.timeout(15000),
    },
  );

  if (response.status !== 204) {
    await parseApiResponse(response, "/api/v1/auth/logout");
  }
}
