## 1. Workspace Foundation

- [x] 1.1 Create the full Sprint 1 directory/file scaffold under `agents/`, `api/`, `dashboard/`, and `data/`.
- [x] 1.2 Add `.env.example`, `requirements.txt`, and `package.json` baseline entries from the build spec.
- [x] 1.3 Scaffold `agents/run_all.py` with startup placeholders for all required agent processes.

## 2. Quickstarter-Aligned Mock Multi-Agent Topology

- [x] 2.1 Implement executor as the orchestrator bridge (Quickstarter pattern) with chat protocol and `/health` + `/message` REST endpoints.
- [x] 2.2 Implement mock supervisor/worker pairs for `health`, `appointment`, `grocery`, and `financial` where supervisor forwards task and worker returns result.
- [x] 2.3 Implement mock `scheduling` agent for direct scheduling-domain responses.
- [x] 2.4 Add shared in-memory request state service for request tracking across executor -> supervisor -> worker -> executor path.
- [x] 2.5 Add environment-driven seed/address config so local mock routing works pre-registration and can switch to Agentverse addresses post-registration.

## 3. Database Schema and Storage Layer

- [x] 3.1 Implement `data/schema.sql` with all Sprint 1 tables, including `org_profile`, `patient_updates`, `action_chat`, `notifications`, and `expiration_notifications`.
- [x] 3.2 Add DB initialization flow to create/open `data/life_graph.db` and apply schema idempotently.
- [x] 3.3 Implement `agents/shared/db.py` org, patient, update, action, chat, notification, caregiver, and scheduling helper functions listed in the spec.
- [x] 3.4 Ensure patient removals are soft deletes (`active=0`) and no delete-based mutation path exists in update helpers.

## 4. Shared Agent Runtime

- [x] 4.1 Implement all required Pydantic message models in `agents/shared/models.py`, including `OnDemandDetectionRequest`.
- [x] 4.2 Implement constants in `agents/shared/constants.py`, including `ORG_CONTEXT_MAP`, `MODIFICATION_ENABLED_DOMAINS`, `DETECTION_TRIGGERS`, and `OVERDUE_SCORE_BOOST`.
- [x] 4.3 Implement `agents/shared/llm.py` with `call_claude`, `call_claude_json`, `call_claude_vision`, and `build_system_prompt()`.
- [x] 4.4 Add startup validation for required env values (`ANTHROPIC_API_KEY`, DB path, internal URLs) with clear error messages.

## 5. Seed Data and Deterministic Checks

- [x] 5.1 Implement `data/seed.py` with seeded org profile, 3 patients, 10 caregivers, patient-caregiver assignments, and one pre-seeded overdue action.
- [x] 5.2 Implement 14-day schedule expansion for each caregiver and insert schedule rows.
- [x] 5.3 Run seed initialization and verify `org_profile` has exactly 1 row.
- [x] 5.4 Verify `caregiver_schedule` has exactly 140 rows.

## 6. Dashboard Bootstrap

- [x] 6.1 Scaffold Vite + React + Tailwind project under `dashboard/`.
- [x] 6.2 Configure React Router with four baseline routes: Action Feed, Patients, Caregivers, Org.
- [x] 6.3 Add minimal AppShell wiring so route navigation is testable before feature views are implemented.

## 7. Human Intervention: Agentverse Registration

- [x] 7.1 [HUMAN] Register required MACOS agents on Agentverse (Executor, Health Supervisor, Appointment Supervisor, Grocery Supervisor, Financial Supervisor, Scheduling Agent, and domain workers if required by deployment model).
- [x] 7.2 [HUMAN] Collect all registered addresses and map them to `.env` (`EXECUTOR_AGENT_ADDRESS`, `HEALTH_SUPERVISOR_ADDRESS`, `APPT_SUPERVISOR_ADDRESS`, `GROCERY_SUPERVISOR_ADDRESS`, `FINANCIAL_SUPERVISOR_ADDRESS`, `SCHEDULING_AGENT_ADDRESS`, plus worker addresses if used).
- [x] 7.3 [HUMAN] Verify the agent address set is complete and recorded for downstream submission/handoff artifacts.

## 8. Human Intervention: ASI:One Orchestration Readiness

- [x] 8.1 [HUMAN] Confirm ASI:One environment access and endpoint/address format to be used for caregiver interactions.
- [x] 8.2 [HUMAN+DEV] Define and document the ASI:One orchestration contract for requester/response message routing aligned to `SchedulingQuery` and `ChatMessage` pathways.
- [x] 8.3 [HUMAN+DEV] Validate null-safe fallback behavior when `asi_one_address` is not configured (dashboard notification path remains primary).
- [x] 8.4 [HUMAN] Record owners and evidence for ASI:One setup so Sprint 5-6 implementation can proceed without discovery work.

## 9. Sprint 1 Exit Criteria

- [x] 9.1 Run foundation smoke check: schema init, seed run, API scaffold start, and all mock agents import/run without runtime errors.
- [x] 9.2 Verify quickstarter-style routing end-to-end: executor receives query, routes to domain supervisor, worker returns result, executor logs/completes response.
- [x] 9.3 Verify executor `/health` and `/message` endpoints respond as expected for local harness checks.
- [x] 9.4 Verify chat protocol handshake: chat acknowledgement emitted and final response returned to sender address.
- [x] 9.5 Confirm Sprint 1 checklist parity against `MACOS_build_spec_v7_final.md` and log unresolved items.
- [x] 9.6 Freeze Sprint 1 outputs and publish a handoff summary for Sprint 2 implementation.
