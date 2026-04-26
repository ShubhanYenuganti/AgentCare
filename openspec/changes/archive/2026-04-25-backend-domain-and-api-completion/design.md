## Context

Sprint 1–2 delivered a working multi-agent scaffold with mock-mode detection and a partial FastAPI contract. All four domain workers currently use a single generic `call_claude_json` prompt to suggest actions — this is not deterministic and does not implement the spec-defined rule checks. The scheduling agent handles only `MockDomainTask` and never runs the real `SchedulingQuery` flow. The FastAPI routers are missing enriched list responses, CORS, caregiver schedule endpoints, and scheduling lifecycle endpoints.

The system architecture is fixed: uagents mesh for agent-to-agent communication, SQLite for persistence, FastAPI for external REST. No changes to those foundations — this change fills in the behavioral and contract gaps within the existing structure.

## Goals / Non-Goals

**Goals:**
- Implement explicit spec-defined detection rule checks in all four domain workers
- Add OpenFDA and Google Maps integrations with proper timeout/retry/fallback
- Add supervisor risk-scoring LLM reassessment pass to all four domains
- Implement health modification pipeline (live-data aware, review, retry, changes summary)
- Implement question live-API branching across all domains
- Replace mock-only scheduling agent with full SchedulingQuery → options → chat-selection → assign/confirm/decline lifecycle
- Complete FastAPI contract: enriched list responses, CORS, scheduling endpoints, caregiver schedule
- Align mock API contracts to spec; add coverage tests
- Complete executor intent handler surface (onboarding, scheduling-query, action-bound, general fallback)
- Soft-delete on removal operations across normalized tables

**Non-Goals:**
- Dashboard or UI implementation (separate change)
- E2E or integration test suites (separate change)
- New database migrations (schema is already aligned from data-layer-seed change)
- Changing the uagents mesh topology or message model contracts

## Decisions

**D1: Explicit rule checks layered above, not replacing, the LLM pass**
Each domain worker will run deterministic rule checks (refill window, appointment overdue threshold, etc.) first and collect rule-triggered drafts. A secondary LLM pass then reviews and may add edge-case drafts. This preserves LLM flexibility while guaranteeing spec-required outputs appear.
- Alternative considered: LLM-only with richer prompts. Rejected — non-deterministic, can't guarantee spec-required checks fire.

**D2: OpenFDA and Google Maps as thin sync wrappers behind `asyncio.to_thread`**
Both external APIs are called synchronously via `httpx` in thread-pool workers, consistent with the existing `call_claude_json` pattern. No new async client framework introduced.
- Alternative: native async httpx. Rejected — adds complexity for calls that are already inside uagents handlers that use `asyncio.to_thread`.

**D3: Risk-scoring pass as a second LLM call in each supervisor**
After workers return drafts, the supervisor makes one `call_claude_json` call to reassess urgency framing and `review_by` recalculation. This is separate from the detection LLM pass and fires unconditionally.
- Alternative: Single merged LLM call with supervisor context. Rejected — supervisor and worker have different context (org-level vs patient-level); keeping them separate is cleaner.

**D4: Scheduling agent keeps MockDomainTask for backward compat, adds SchedulingQuery handler**
A new `@agent.on_message(SchedulingQuery)` handler is added alongside the existing mock handler. Executor routes scheduling intents to the new handler. Mock handler is retained so existing mock-mode tests don't break.
- Alternative: Replace mock handler entirely. Rejected — would break existing test flows before the test change lands.

**D5: Soft-delete via `UPDATE … SET active=0` rather than DELETE**
All removal operations across `medications`, `appointments`, `grocery`, `financial_bills`, etc. set `active=0`. Read queries already filter `WHERE active=1` from the data-layer work. No schema changes needed.

**D6: Non-health modification guard in supervisor**
Appointment, grocery, and financial supervisors return a `ModificationResult` with `revised_draft="not_supported"` and `changes_summary="Modification not supported for this domain"` when they receive a `ModificationRequest`. No worker delegation.
- Alternative: Raise an error. Rejected — executor already handles `ModificationResult`; an error response would require new error routing code.

## Risks / Trade-offs

- [OpenFDA rate limits] → Use a 2-second timeout with one retry; fall back to `{"status": "lookup_unavailable"}` so detection continues without the API result.
- [Google Maps API key absent in dev] → Guard with `os.getenv("GOOGLE_MAPS_API_KEY")`; skip transport planning step and log a warning when key is missing. Appointment worker still produces non-transport drafts.
- [Scheduling chat-selection requires in-flight state] → Use `InMemoryRequestState` (already exists) to track pending scheduling queries keyed by `action_id`. Stale entries removed by the existing 900s expiration loop.
- [Risk-scoring LLM call adds latency to every detection pass] → Accept; the supervisor-to-executor path already has a 30s timeout budget. Risk scoring is a single small call (~200 tokens) after all workers return.
- [Mock API contract changes may break existing approval flow tests] → Changes are additive only (response envelope enrichment). Existing fields preserved.
