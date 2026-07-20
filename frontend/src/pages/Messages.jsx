import PagePlaceholder from "./PagePlaceholder";

// RESERVED: full message log, reusing MessageFlowFeed with a longer
// list + a search/filter bar (filter by agent, by kind: request/response).
export default function Messages() {
  return (
    <PagePlaceholder
      title="Messages"
      description="Full agent-to-agent message log with search/filter goes here."
    />
  );
}
