# Phase 10 browser acceptance

Validated 7 October 2026 through the Codex in-app browser against disposable localhost API 8019 / frontend 5179. All provider responses were deterministic fixtures; no live Google/Groq request occurred.

1. PASS — Authenticated disposable session opens Personal Workspace with empty evidence
2. PASS — Run composer has initial goal focus, disabled empty submission, and native modal
3. PASS — Single completes with one Direct stage, zero handoffs, saved output and measured tokens
4. PASS — Fixed completes Research/Data/Analysis/Summarizer/Report with five stage starts and four handoffs
5. PASS — Adaptive analysis selects Analysis → Report, records skipped agents and rules-v1, with two starts and one handoff
6. PASS — Exact persisted handoff opens with message identity, payload and source/receiver
7. PASS — Event History renders saved events and explicitly says it does not rerun agents
8. PASS — Provider failure is explicit, downstream stages never execute, missing usage stays unavailable, and no success output is fabricated
9. PASS — History retains all three modes plus the failed run with metrics
10. PASS — Recycle confirmation Escape cancels and returns focus to its trigger
11. PASS — Recycled completed run remains listed with authenticated actor and retained-evidence warning
12. PASS — Restore returns the original run and metrics to active history
13. PASS — Agent loading error is surfaced and Refresh agents and runs successfully recovers
14. PASS — Custom agent saves revision 1 with fingerprint and produces persistent one-stage execution output
15. PASS — Switching from Personal Workspace clears prior simulation evidence and loads organization-scoped research
16. PASS — Research compares 42 retained trials with per-cell sample counts, unknown human quality and explicit fixture/descriptive labels
17. PASS — Export preview contains all 42 Task/stage/provenance records with unknown cost and no live/global conclusion
18. PASS — Hiring loading/read error is explicit; Reload recovers persisted organization records
19. PASS — Requirement revision 2 shows exact revision history and source-specific JD/AI navigation
20. PASS — Human JD revision 1 is persisted with requirement revision 2 and knowledge revision 2
21. PASS — Recruiter runs exact-source JD proposal; result is labeled AI proposal and human validation action is disabled without Reviewer authority
22. PASS — Recruiter submits exact human JD revision 1; record retains actor and pinned requirement/knowledge, with no review/approve controls
23. PASS — Distinct Reviewer can request changes but cannot approve; explicit confirmation appends immutable attributed revision-1 history
24. PASS — Change request leads to explicit human revision 2, which needs a new submission and retains prior history
25. PASS — Distinct Reviewer recommends revision 2; revision-1 change request remains superseded and immutable
26. PASS — Distinct Approver explicitly approves revision 2; Recruiter/Reviewer/Approver actors and immutable decision chain remain visible
27. PASS — Human decision Escape cancellation returns focus and records no decision before explicit confirmation
28. PASS — New JD revision 3 explicitly shows earlier approval applies only to revision 2 and requires a separate submission
29. PASS — Revision-3 rejection is attributed to Approver and leaves superseded revision-2 approval intact
30. PASS — Approver HR review authority permits exact JD validation but disables Recruiter analysis/proposal actions
31. PASS — Validation retains requirement/knowledge/JD revisions, fingerprints, Task/stage status and actual fixture usage
32. PASS — Personal Workspace excludes HR records and immediately clears old organization content
33. PASS — IAM-only organization Owner is denied HR access; ownership does not convey HR roles
34. PASS — Narrow viewport reports 650px actual width with no document overflow and usable navigation/denial state
35. PASS — Recruiter requirement assessment completes as a structured proposal; all three specialized HR actions are exercised
36. PASS — Research Lab admits a new one-case Single/Fixed/Adaptive fixture experiment, showing 1/1 trials and unknown SD at n=1
37. PASS — All seven rubric fields save with actor, output binding and explicit fixture-only rationale; deterministic/human scores stay separate
38. PASS — Same-configuration rerun creates three fresh runs, preserves original experiment and records parent provenance
39. PASS — Custom-agent immutable revision history and original execution remain available after workspace switching
40. PASS — Organizations presents IAM access roles separately from HR responsibilities and protects the last-owner contract
41. PASS — Switching immediately after starting a delayed JD revision read discards old content in the IAM-only workspace
42. PASS — Sign out revokes the synthetic application session and returns to the authentication page without invoking Google

Result: 42 final checkpoints passed; 0 unresolved checkpoint failures; 0 skipped checkpoints.

Transient fetch failures were surfaced in Agents, Hiring and Research Lab. Explicit refresh/reload recovered them; no failure was hidden. Their transport root cause was not established. Download preview/export content was verified; a saved browser file download is not claimed. The requested 390px viewport was clamped by the in-app browser to 650px; actual 650px layout was inspected and the override was reset. This is sampled browser/keyboard acceptance, not exhaustive mobile or assistive-technology certification. Entered human rubric values were explicitly fixture UI acceptance, not independent research evaluation.
