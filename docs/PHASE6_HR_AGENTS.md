# Phase 6 — Specialized HR assistance

The verified Phase 5 workflow is requirements → optional organization knowledge →
human-authored JD → review. No prior explicit specialized catalog exists in the
repository. The smallest complete catalog therefore has three identities:

| Identity | Purpose | Required sources | HR permission | Output |
| --- | --- | --- | --- | --- |
| hr_requirement_analysis | Assess missing, ambiguous and contradictory requirement information | Requirement revision; optional knowledge revision | JD_DRAFT_EDIT (Recruiter) | Summary and categorized source/field findings |
| hr_jd_draft | Propose description using organizational knowledge | Requirement revision; optional knowledge revision | JD_DRAFT_EDIT (Recruiter) | Structured description and human review notes |
| hr_draft_validation | Compare saved description with its sources | Description revision plus its exact requirement and optional knowledge revisions | JD_REVIEW (Reviewer or Approver) | Summary and categorized source/field findings |

Role interpretation is integrated into assessment/drafting/validation, rather than
creating a fourth agent. No candidate, screening or employment decision workflow
is added. Existing six system identities and custom agents are unchanged.

All source references are stable IDs plus positive revision numbers. Admission
reads source history inside one authenticated tenant transaction, checks live IAM
and HR roles first, and creates a frozen ExecutionContext containing canonical
JSON source snapshots. Inputs exceeding 18,000 source characters fail before
admission; sources are never silently truncated. Validation must match the saved
JD's exact source references. Historical/archived source revisions remain usable
for assistance; this does not change foundation lifecycle rules for new human JDs.

Provider selection uses the existing `llm_client.call_llm` Groq adapter and server
GROQ_MODEL setting. Implementation version 1 uses a fixed system prompt, an explicit
JSON schema and no tools, URLs, shell, browsing or file retrieval. Source text is
untrusted data, including organization knowledge. Model findings must cite supplied
source fields; supported claims still require human review. Output JSON rejects
unknown fields including approval/publication or IAM claims. AI proposals do not
modify or create authoritative HR records. Human decisions remain outside Phase 6.

Task and StageExecution remain the execution authority. The additive Task
`hrExecution` payload stores the validated request, implementation version, provider,
configured model, exact source fingerprints/references, ExecutionContext snapshot,
system prompt and output schema. Successful structured JSON lives in existing Task
and StageExecution output, not another results table. Stage model and usage come
from the actual adapter response; unavailable metrics remain null. Validation
failures after a response retain measured usage but discard invalid output.

`GET /api/v1/hiring/agents` discovers live role capabilities. `POST /runs` under that
prefix returns 202 and a queued task; `GET /runs` lists retained HR executions and
`GET /runs/{id}` retrieves authoritative status and structured evidence. Every
submission creates a fresh run; no automatic paid retry or resume is performed.
The worker claims an admitted task once, rechecks live source authorization before
provider invocation and before accepting output. Timeout is configured only in
`core/config.py` via HR_AGENT_TIMEOUT_SECONDS (default 90 seconds). Cancellation
and provider/contract failures produce honest terminal evidence with fixed safe
errors, without exception text or credentials. Existing startup interruption
recovery covers HR tasks. No LangGraph activation or checkpoint runtime change.

Generic simulation list/get projections exclude HR executions. Existing recycle-bin
lifecycle retains their evidence and requires HR read authority as well as IAM.
HR results use authenticated polling rather than workspace-wide WebSocket output
broadcasts. PostgreSQL simulation RLS adds an HR-domain guard for `task_type =
'hr_agent'`; child evidence inherits that parent policy. Existing startup maintenance
principal retains bounded recovery/finalization access after revocation. Worker
finalization requires identical admission input/ownership and an existing pending
HR task. No new tables, columns or schema version are needed: operational schema
remains 12, with startup refreshing the reviewed RLS policies. SQLite enforces the
same request/repository boundaries; PostgreSQL independently forces RLS.

The general `/tasks`/`simulations` admission path rejects the reserved `hr_agent`
task type. Task validation binds HR evidence to its owner/workspace, agent and
single stage. Generic tenant queries exclude HR rows in SQL before retrieving
payloads. Specialized retrieval checks HR permission before reading evidence.

The HR Hiring page contains action discovery, record and exact revision selectors,
server-admitted run identity, polling of queued/running status, structured proposals,
safe failures and persisted history. Validation automatically uses the selected
human draft's historical sources. Workspace switching remounts the interface;
obsolete responses cannot restore previous tenant results. No proposal is copied
into a foundation record automatically, and no approval/publication UI is added.

Browser fixture: `backend/tests/hr_agents_browser_fixture.py` starts a disposable
SQLite server on 127.0.0.1:8019 and a local session endpoint. It patches only the
provider adapter with deterministic responses and a deliberate failure, waits
1.5 seconds to exercise progress, and contains no credentials. Never import it
in production. Frontend acceptance uses VITE_API_BASE_URL=http://127.0.0.1:8019 on
127.0.0.1:5179. Live paid calls were not made; real provider acceptance remains
unverified. No package installation, deployment or production activation is needed.
