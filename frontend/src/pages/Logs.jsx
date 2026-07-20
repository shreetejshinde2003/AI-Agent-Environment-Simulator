import PagePlaceholder from "./PagePlaceholder";

// RESERVED: raw timestamped event log — this is the direct read-out of
// backend/app/websocket/manager.py's broadcast history once storage
// (backend/app/storage/) is persisting events instead of just
// broadcasting them live.
export default function Logs() {
  return (
    <PagePlaceholder
      title="Logs"
      description="Raw timestamped event log goes here — the un-summarized version of the Activity Feed."
    />
  );
}
