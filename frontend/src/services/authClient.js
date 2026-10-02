import { API_BASE_URL } from "./apiClient";

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

  if (response.status === 401) {
    return null;
  }

  if (!response.ok) {
    throw new Error(
      `Authentication check failed (${response.status})`,
    );
  }

  const payload = await response.json();

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

  if (!response.ok && response.status !== 204) {
    throw new Error(
      `Sign out failed (${response.status})`,
    );
  }
}
