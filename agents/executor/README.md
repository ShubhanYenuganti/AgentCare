# Executor Agent

The executor is the orchestration boundary for Autocare.
It receives requests from API/chat surfaces, classifies intent, dispatches to domain supervisors, aggregates responses, and runs background health/expiration loops.

## Runtime role
- Classifies incoming requests into `detection`, `question`, or `modification`.
- Resolves patient context for routing.
- Fans out detection to domain supervisors (`health`, `appointment`, `grocery`, `financial`).
- Routes task-scoped question/modification requests to the selected domain supervisor.
- Supports general chat drafting via `/general-chat` and revision via `/general-chat/revise`.
- Runs expiration escalation loop (dashboard + ASI:One channels with dedup).

## HTTP endpoints (port 8001)
- `GET /health`
- `POST /message`
- `POST /general-chat`
- `POST /general-chat/revise`
- `POST /internal/detect`
- `POST /internal/expiration-check`
- `GET /mailbox-debug`

## Detection fan-out contract
Inbound: `OnDemandDetectionRequest` (internal trigger path) or executor-built fan-out payload.
Outbound per domain: `OnDemandDetectionRequest` to supervisor.
Return path: supervisors send `SupervisorResult`; executor finalizes fan-out state.

## Question/Modification routing
- Question path: `QuestionRequest` -> domain supervisor -> `QuestionAnswer`.
- Modification path: `ModificationRequest` -> domain supervisor -> `ModificationResult`.
- Current policy from shared constants: modification is enabled for health domain workflows.

## Expiration + overdue pipeline
- Interval job: every 900s.
- Overdue criteria: pending action with `review_by < now` and `is_overdue=0`.
- Effects:
  - marks action overdue,
  - writes dashboard notification,
  - sends ASI:One `ChatMessage` if `ASI_ONE_AGENT_ADDRESS` is configured,
  - logs channel dedup in `expiration_notifications`.
- Immediate trigger endpoint: `POST /internal/expiration-check` (supports optional forced-overdue action).

## Protocol integration
- Chat protocol (`executor-chat`) is enabled for Agentverse mailbox ingress.
- Uses `LocalFirstResolver` for low-latency intra-stack routing, falls back to global resolver for external addresses.

## Running
```bash
python -m agents.executor.agent
```
