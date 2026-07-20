import PagePlaceholder from "./PagePlaceholder";

// RESERVED: this is the big one — full scrubbable replay of a past
// simulation using LangGraph's checkpointing (see
// backend/app/agents/orchestrator.py). Reuses AgentRelationshipGraph +
// SimulationTimeline but driven by historical state snapshots instead
// of live data.
export default function Replay() {
  return (
    <PagePlaceholder
      title="Replay"
      description="Scrub through a completed simulation using LangGraph's checkpointed state history."
    />
  );
}
