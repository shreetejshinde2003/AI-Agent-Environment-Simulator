// Browser messages are hints only. /auth/me and the session cookie are authority.
let expectedUserId = null;
export function setExpectedUser(user) { expectedUserId = user?.id ?? null; }
export function sessionHeaders() {
  return expectedUserId ? {"X-Expected-User-Id": expectedUserId} : {};
}

export function announceSessionChange() {
  try {
    const channel = new BroadcastChannel("fmproject-session");
    channel.postMessage("recheck");
    channel.close();
  } catch { /* Focus and periodic checks also work without browser storage. */ }
}

export function watchSessionChanges(recheck) {
  const focus = () => recheck();
  const visible = () => { if (document.visibilityState === "visible") recheck(); };
  let channel;
  try {
    channel = new BroadcastChannel("fmproject-session");
    channel.onmessage = focus;
  } catch { /* Notifications are optional. */ }
  window.addEventListener("focus", focus);
  document.addEventListener("visibilitychange", visible);
  const timer = window.setInterval(visible, 15000);
  return () => {
    channel?.close();
    window.clearInterval(timer);
    window.removeEventListener("focus", focus);
    document.removeEventListener("visibilitychange", visible);
  };
}
