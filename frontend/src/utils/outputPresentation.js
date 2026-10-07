// Presentation only. Callers retain the exact persisted response for Raw view.
export function requestedFormat(directive = "") {
  directive = directive.split(/(?:^|\n)(?:source|text):/i)[0];
  if (/\b(?:return|give|output|respond|produce)(?:\s+\w+){0,3}\s+json\b/i.test(directive)) return "json";
  if (/\bplain text\b/i.test(directive)) return "text";
  if (/\bmarkdown\b|\bbullet(?:s| points)?\b/i.test(directive)) return "markdown";
  return "auto";
}
export function presentOutput(raw, directive = "", recordedContract) {
  const recordedFormat = recordedContract?.format === "text" && requestedFormat(directive) === "auto" ? "auto" : recordedContract?.format;
  const format = recordedFormat === "bullets" ? "markdown" : recordedFormat ?? requestedFormat(directive);
  let text = raw?.trim() ?? "";
  const changes = [];
  const preserveQuotes = /(?:surrounded by|in|with|include)\s+(?:quotation marks|quotes|a quoted string)|(?:return|produce)\s+(?:a\s+)?quoted\s+string/i.test(directive.split(/(?:^|\n)(?:source|text):/i)[0]);
  for (let n = 0; !preserveQuotes && n < 3; n++) {
    try {
      const decoded = JSON.parse(text);
      if (typeof decoded !== "string") break;
      if (format === "json") {
        let nested;
        try { nested = JSON.parse(decoded); } catch { break; }
        if (nested == null || typeof nested !== "object") break;
      }
      text = decoded.trim(); changes.push("serialized_string");
    } catch { break; }
  }
  const fence = text.match(/^```(?:text|plaintext|markdown|md|json)?\s*\n([\s\S]*?)\n```$/);
  // Keep fences if the user explicitly requested code/fences.
  if (fence && !/\b(?:code|fence)\b/i.test(directive)) {text = fence[1]; changes.push("outer_code_fence");}
  if (/^"""[\s\S]*"""$/.test(text) && format === "text" && !preserveQuotes) {text = text.slice(3,-3);changes.push("triple_quote_wrapper");}
  let json;
  try {json = JSON.parse(text);} catch { /* Show malformed JSON as text with an explicit issue. */ }
  const issues = [...new Set([...(recordedContract?.issues ?? []), ...changes])];
  if (format === "json" && json === undefined) issues.push("invalid_json");
  const type = format === "json" || (format === "auto" && json != null && typeof json === "object") ? "json" :
    format === "markdown" || format === "auto" && /(^#{1,6} |^[-*+] |\*\*|^```|^\|)/m.test(text) ? "markdown" : "text";
  return {text: type === "json" && json !== undefined ? JSON.stringify(json,null,2) : text, type, issues};
}
