export const emptyAgentConfig = {
  name: "", description: "", purpose: "", instructions: "",
  inputContract: "text", outputContract: "text", provider: "groq", model: "default",
  capability: "text_generation", maxTokens: 1024, timeoutSeconds: 60, active: true,
};
export function canManageAgents(workspace) {
  return workspace?.kind === "personal" || ["owner", "admin"].includes(workspace?.membershipRole);
}
export function validateAgentConfig(config) {
  for (const [field, max] of [["name", 80], ["purpose", 1000], ["instructions", 8000]]) {
    if (!config[field]?.trim()) return `${field[0].toUpperCase() + field.slice(1)} is required.`;
    if (config[field].trim().length > max) return `${field} must be at most ${max} characters.`;
  }
  if ((config.description?.trim().length ?? 0) > 1000) return "Description must be at most 1000 characters.";
  if (!["default", "fast"].includes(config.model) || config.provider !== "groq" ||
      config.inputContract !== "text" || config.outputContract !== "text" || config.capability !== "text_generation") return "Unsupported agent configuration.";
  if (!Number.isInteger(config.maxTokens) || config.maxTokens < 64 || config.maxTokens > 1024) return "Output token limit must be between 64 and 1024.";
  if (!Number.isInteger(config.timeoutSeconds) || config.timeoutSeconds < 1 || config.timeoutSeconds > 120) return "Timeout must be between 1 and 120 seconds.";
  return null;
}
export function validateAgentInput(text) {
  return !text.trim() ? "Enter text to run the saved agent." : text.trim().length > 10000 ? "Input must be at most 10000 characters." : null;
}
