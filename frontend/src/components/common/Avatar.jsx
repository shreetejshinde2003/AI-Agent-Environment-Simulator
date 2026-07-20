import "./Avatar.css";

/**
 * Avatar — small colored circle with an initial, used for agents
 * without a custom icon (Message Flow, Activity Feed rows).
 */
export default function Avatar({ name, color, size = 28 }) {
  const initial = (name ?? "?").charAt(0).toUpperCase();

  return (
    <div
      className="avatar"
      style={{ width: size, height: size, background: color, fontSize: size * 0.42 }}
      aria-hidden="true"
    >
      {initial}
    </div>
  );
}
