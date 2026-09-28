# V1 audit and validation

Audit performed 2026-09-28 before implementation. Actual repository behavior,
not old README claims, defined the implementation. Production was inspected
read-only; no public tasks, settings or deployment configuration were changed.

## Phase 0 audit matrix

| Feature | Current UI at audit | Backend support at audit | Real or mock | Missing work | Phase |
|---|---|---|---|---|---|
| Five-stage execution | Full pipeline choice, result panel | Sequential Groq calls and exact context handoffs | Real | Preserve engine; original directive in downstream prompts | 1–2 |
| Agent graph | Static hub with animated relationships, Web Search idle | Roster plus hardcoded active edges | Mock topology/activity | Run-specific states and actual handoffs | 6 |
| Simulation identity | Session-level totals | In-memory task dictionaries only | Partial | Per-run records, lifecycle and storage | 3–4 |
| Timeline / Replay | Empty timeline; Replay expects an array but receives object | No persisted event history | Disconnected | Timestamp events and honest event navigation | 5, 7 |
| Message flow | Large real payloads, no run scoping | Four real handoffs per pipeline | Real but fragmented | Run linkage, preview/details, graph edges | 8 |
| Metrics/charts | Partial session metrics, no useful historical charts | Runtime counters; repeated-failure averages unreliable | Mixed/incomplete | Persist stage usage/durations, aggregate authoritative history | 9–10 |
| Task history/results | Selection forced to latest on refresh; incomplete detail | Results lost after restart | Partial | Stable selection, saved run details and reopen | 11 |
| Upload / preview | No working feature | None | Absent | Safe parsers and actual prompt context | 12–13 |
| Export / clear | Console TODO quick actions | No export | Disconnected | Real downloads; do not expose fake destructive controls | 14 |
| User/settings | Hardcoded administrator; saved switches do not change client | No authentication/users | Mock identity | Shared-workspace disclosure; nullable ownership | 15 |
| Web Search | Shown idle/selectable as placeholder | process raises NotImplementedError | Not implemented | Keep unavailable, no invented browsing | 16 |
| Failure view | Task error only, graph not stage-aware | Pipeline already stops on error | Partly real | Persist failed stage, timeline, truthful downstream waiting | 17 |
| Pause/resume/stop | Enabled controls with TODO handlers | Flags only; cannot interrupt LLM HTTP calls | Fake control semantics | Disabled UI, explicit unsupported API result | 18 |
| WebSocket/config | No reconnect; separate localhost fallback | Broadcast works; CORS permits Vercel | Partial | Derive URL, reconnect+REST recovery, no production localhost default | 19 |
| Documentation/prototypes | README says Ollama/agents reserved | Groq and five implementations active | Stale | Update active docs; isolate unused LangGraph/SQLAlchemy/demo prototypes | 0, 20 |

The public app connected to Railway and displayed two completed tasks and eight
real messages at audit time. The graph did not represent their execution.
An observed final result drifted from the original requested deliverable.
No real upload, export, timeline or private user identity was available.

## Implementation boundaries

- Existing sequential execution remains in tasks.py; no LangGraph import was added.
- SQLite snapshot schema v1: simulations(id, owner_id, status, created_at, payload),
  uploads(id, payload), agent_roster(id, payload). Nested records are versioned
  with the application schema. No credentials or original binary files are stored.
- Legacy task JSON remains camelCase with in_progress. New simulations project
  this as running. Stage states are waiting/active/completed/failed.
- Existing task/message/activity broadcasts remain; lifecycle and stage events
  are additive. The frontend refetches REST after socket reconnect and polls as
  a recovery fallback. Offline data is clearly labeled stale.
- React Flow was already installed. No runtime dependencies were added.
- No auth claim: owner_id is nullable, all records are shared. Public confidential
  uploads and private ownership require authentication in a later milestone.
- Web Search, PDF, request cancellation, automatic retries, distributed workers
  and production durable-volume provisioning remain outside implemented V1.

## Validation evidence

Mocked backend tests cover exact handoffs/order, original directive in every
agent prompt, output storage, failure at each stage, empty output, standalone
mode, unavailable agents, context isolation, uploads, events, exports, metrics,
restart recovery, credential redaction and malformed input.

One real local browser-created Groq run used a 186-byte TXT reference and a short
REST API directive. Run T-c330cc42f3bb completed with 17 events, 4 exact handoffs,
5 stages, 3,717 provider-reported tokens and a 528-character final Report result
in 7.827 seconds. Model: openai/gpt-oss-120b. No credentials were displayed.

| Stage | Output characters | Tokens | Duration (seconds) |
|---|---:|---:|---:|
| Research | 464 | 456 | 1.610 |
| Data | 1093 | 1054 | 1.999 |
| Analysis | 516 | 897 | 1.448 |
| Summarizer | 457 | 743 | 1.490 |
| Report | 528 | 567 | 1.234 |

A separate explicitly labeled mocked failure run in the isolated local test
database failed at Analysis: Research/Data completed; Analysis failed;
Summarizer/Report stayed waiting; progress 40%; no final report; no token
measurements invented. Its graph, timeline, messages and aggregate failure
count were visible. These test fixtures are not seeded in application code.

## Operational limits

Run a single FastAPI worker. SQLite is sufficient for a local workspace, not a
distributed queue. History reads currently load full snapshots; pagination,
retention, rate limits, bounded concurrent provider calls, and archival uploads
are later scaling work. Provider timeouts/retries follow the existing Groq SDK.

The prompt contract reduces fabrication but cannot guarantee factual correctness
or perfect formatting. Outputs remain actual provider responses, not repaired
or replaced with fabricated success.

Railway needs an approved durable-volume/database decision for history across
deployments; the default ephemeral filesystem is insufficient. No volume, service,
environment file, secret, Groq model, Vercel setting or Railway setting was changed.
Existing backend/.env remains working-directory relative. The frontend uses its
configured API origin and derives wss for HTTPS. CORS configuration is unchanged.
