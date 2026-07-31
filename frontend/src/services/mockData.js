/**
 * services/mockData.js
 *
 * DEMO MODE ONLY — this data is used exclusively when VITE_DEMO_MODE=true
 * or the URL has ?demo=true (see hooks/useSimulationData.js). It is
 * NOT the default anymore: with no backend connected, the app shows
 * genuine zero/empty values (see EMPTY_STATE in useSimulationData.js),
 * not this fake data. That's intentional — a real-time dashboard
 * should never claim agents are active when nothing is running.
 *
 * Shaped EXACTLY like the backend's real API responses (see
 * backend/app/models/schemas.py and backend/app/api/routes/*.py — the
 * field names here match on purpose), so demo mode and real mode are
 * visually indistinguishable except for the "Demo Mode" badge.
 */

export const mockAgents = [
  { id: "orchestrator", name: "Orchestrator", role: "orchestrator", status: "active", color: "#8b5cf6" },
  { id: "research", name: "Research Agent", role: "research", status: "active", color: "#3b82f6" },
  { id: "data", name: "Data Agent", role: "data", status: "active", color: "#22c55e" },
  { id: "web_search", name: "Web Search Agent", role: "web_search", status: "active", color: "#f59e0b" },
  { id: "analysis", name: "Analysis Agent", role: "analysis", status: "active", color: "#eab308" },
  { id: "summarizer", name: "Summarizer Agent", role: "summarizer", status: "active", color: "#14b8a6" },
  { id: "report", name: "Report Agent", role: "report", status: "idle", color: "#ec4899" },
];

export const mockRelationships = [
  { sourceAgentId: "orchestrator", targetAgentId: "research", type: "dependency", active: true },
  { sourceAgentId: "orchestrator", targetAgentId: "data", type: "dependency", active: true },
  { sourceAgentId: "orchestrator", targetAgentId: "web_search", type: "dependency", active: true },
  { sourceAgentId: "orchestrator", targetAgentId: "analysis", type: "dependency", active: true },
  { sourceAgentId: "orchestrator", targetAgentId: "summarizer", type: "dependency", active: true },
  { sourceAgentId: "orchestrator", targetAgentId: "report", type: "dependency", active: false },
  { sourceAgentId: "research", targetAgentId: "data", type: "data_flow", active: true },
  { sourceAgentId: "web_search", targetAgentId: "orchestrator", type: "message", active: true },
  { sourceAgentId: "summarizer", targetAgentId: "report", type: "data_flow", active: false },
];

export const mockTasks = [
  {
    id: "T-1024",
    directive:
      "Search for top competitors in the AI market and collect key information like product, pricing, and recent news.",
    assignedAgentId: "web_search",
    status: "in_progress",
    priority: "high",
    startedAt: new Date(Date.now() - 150_000).toISOString(),
    durationSeconds: 150,
    progressPercent: 65,
    progressSteps: [
      { label: "Identified 12 competitor websites", done: true },
      { label: "Extracted basic company information", done: true },
      { label: "Collecting pricing and product details", done: false },
      { label: "Compiling results", done: false },
    ],
    output: null,
    error: null,
  },
  {
    id: "T-1023",
    directive: "Summarize recent trends in on-device AI inference.",
    assignedAgentId: "research",
    status: "completed",
    priority: "medium",
    startedAt: new Date(Date.now() - 400_000).toISOString(),
    durationSeconds: 38,
    progressPercent: 100,
    progressSteps: [{ label: "research completed the task", done: true }],
    output:
      "## Research Findings\n\nOn-device inference has shifted toward smaller, quantized models (2B-8B parameters) that run acceptably on consumer hardware. Key drivers: privacy-sensitive use cases, offline reliability, and falling per-token cloud costs no longer being the only lever. Frameworks like Ollama and llama.cpp have made local deployment far more accessible to small teams.\n\n(Demo Mode sample output — not a real agent response.)",
    error: null,
  },
];

export const mockMessages = [
  {
    id: "m1",
    fromAgentId: "research",
    toAgentId: "data",
    kind: "request",
    content: "Please extract structured data from sources",
    timestamp: new Date(Date.now() - 45_000).toISOString(),
  },
  {
    id: "m2",
    fromAgentId: "data",
    toAgentId: "analysis",
    kind: "response",
    content: "Extracted 42 records successfully",
    timestamp: new Date(Date.now() - 37_000).toISOString(),
  },
  {
    id: "m3",
    fromAgentId: "analysis",
    toAgentId: "summarizer",
    kind: "request",
    content: "Please generate insights summary",
    timestamp: new Date(Date.now() - 20_000).toISOString(),
  },
  {
    id: "m4",
    fromAgentId: "summarizer",
    toAgentId: "report",
    kind: "response",
    content: "Summary generated. Preparing report.",
    timestamp: new Date(Date.now() - 5_000).toISOString(),
  },
];

export const mockActivity = [
  { id: "a1", agentId: "analysis", text: "completed data analysis", timestamp: new Date(Date.now() - 5_000).toISOString() },
  { id: "a2", agentId: "data", text: "extracted 42 records", timestamp: new Date(Date.now() - 10_000).toISOString() },
  { id: "a3", agentId: "web_search", text: "found 15 relevant sources", timestamp: new Date(Date.now() - 22_000).toISOString() },
  { id: "a4", agentId: "research", text: "started collecting market trends", timestamp: new Date(Date.now() - 45_000).toISOString() },
  { id: "a5", agentId: "orchestrator", text: "assigned task to Research Agent", timestamp: new Date(Date.now() - 60_000).toISOString() },
];

export const mockStats = {
  simulationId: "SIM-2024-05-12-001",
  status: "running",
  startTime: new Date(Date.now() - 765_000).toISOString(),
  durationSeconds: 765,
  totalAgents: 7,
  activeAgents: 6,
  totalTasks: 28,
  completedTasks: 17,
  totalMessages: 142,
  avgResponseTimeSeconds: 2.34,
  successRatePercent: 95.2,
};

/** Per-agent timeline segments for the Simulation Timeline chart.
 *  Each segment is [startSeconds, endSeconds] relative to simulation start. */
export const mockTimeline = {
  "Research Agent": [[0, 15]],
  "Data Agent": [[5, 12], [18, 26]],
  "Web Search Agent": [[0, 10], [14, 22], [24, 30]],
  "Analysis Agent": [[0, 8], [16, 24]],
  "Summarizer Agent": [[10, 24]],
  "Report Agent": [[18, 22]],
  Orchestrator: [[0, 30]],
};
