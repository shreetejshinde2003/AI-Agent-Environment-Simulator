// React escapes model/upload text. Never interpret HTML or present a preview as
// the complete record; the full text remains selectable and keyboard-accessible.
export default function RecordedText({text, label = "recorded text", limit = 1400}) {
  if (text == null) return <p className="empty-note">No {label} recorded.</p>;
  if (text === "") return <p className="empty-note">Recorded {label} is empty (0 characters).</p>;
  const long = text.length > limit;
  return <div className="recorded-text">
    {long ? <><div className="recorded-text-body" role="region" tabIndex="0" aria-label={`${label} preview`}>{text.slice(0, limit)}…</div>
      <details><summary>Show full {label} · {text.length.toLocaleString()} characters</summary>
        <div className="recorded-text-body recorded-text-full" role="region" tabIndex="0" aria-label={`Full ${label}`}>{text}</div>
      </details></> : <div className="recorded-text-body" role="region" tabIndex="0" aria-label={label}>{text}</div>}
  </div>;
}
