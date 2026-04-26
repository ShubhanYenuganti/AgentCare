## Context

The Autocare multi-agent stack already supports action-bound chat (`/actions/{id}/chat`) where the executor receives a message pre-annotated with an existing action ID. There is no equivalent surface for freeform, context-free queries — caregivers who want to ask a general question or initiate a new action must know in advance which action to open, which breaks the conversational discovery use case.

The executor already has intent classification (`question`, `modification`, `scheduling`, `detection`) and a general-query fallback path. This design extends that machinery with a `create-action` intent class, a multi-turn clarification loop, a transient staging layer, and a new React chatbot panel.

## Goals / Non-Goals

**Goals:**
- Freeform chat endpoint decoupled from any existing action ID
- Executor-driven classification: `question` (answered inline) vs `create-action` (draft workflow)
- Domain and patient resolution as part of classification
- Multi-turn clarification loop: executor proposes assumptions, caregiver confirms or corrects
- Transient staging for draft actions — zero DB writes until caregiver approves
- Approve/Discard/Modify controls on the draft card in the chat UI
- On Modify: executor receives original draft + caregiver feedback, produces a revised draft (same loop, no extra round-trip to supervisor)
- On Approve: draft flushed to `action_history`, appears in ActionFeed
- On Discard: staged draft deleted, no side-effects

**Non-Goals:**
- Streaming token-by-token responses (request/response is sufficient at this scale)
- Voice input
- Multi-patient bulk action creation from a single chat turn
- Modifying or replying within the existing action-bound chat thread

## Decisions

### 1. Session-scoped conversation state lives in the DB, not in-memory

**Decision**: Use a `chat_sessions` table with a `session_id` (UUID) and a `chat_messages` table (role, content, intent_class, domain, patient_ids, stage). The frontend passes `session_id` on every request.

**Rationale**: The executor process may restart between turns. In-memory session state would be lost, breaking the clarification loop. DB persistence is consistent with how action chat already works and costs almost nothing at this scale.

**Alternative considered**: Redis session cache. Rejected — adds an infra dependency for a single-node demo stack.

---

### 2. Staging state is a `staged_actions` table row, not a flag on `action_history`

**Decision**: Draft actions are written to a separate `staged_actions` table with `session_id`, `draft_payload` (JSON), and `status` (`pending_approval` | `discarded` | `committed`). On Approve, the executor copies the payload into `action_history` and marks staged row as `committed`. On Discard, it marks `discarded`. No orphan rows ever appear in `action_history`.

**Rationale**: Keeps the primary action feed clean. A flag on `action_history` would require filtering everywhere action data is read. A separate table is surgically isolated.

**Alternative considered**: Keep draft only in the chat message content, never persist to a DB row until approval. Rejected — the Modify flow needs the executor to recover the original draft by ID without relying on frontend-provided payload (security boundary).

---

### 3. Clarification loop is driven by the executor, not the frontend

**Decision**: After classification, the executor composes a clarification message listing its assumptions (intent, domain, patient name) and returns it as an `agent` role chat message with `stage: "clarifying"`. The frontend renders it as a regular message. The caregiver replies with plain text ("yes", "actually it's Robert", etc.). The executor re-evaluates on the next turn.

**Rationale**: Keeps the frontend stateless. The executor owns all conversation logic, which is consistent with how the rest of the agent stack works.

**Alternative considered**: Frontend renders a structured "confirm assumptions" card with Yes/Edit buttons. Rejected — harder to build generically and the executor already has LLM capacity to parse free-text confirmations.

---

### 4. `create-action` intent routes to the same supervisor-worker as the resolved domain

**Decision**: Once the caregiver confirms assumptions, the executor sends a `QuestionTask` (repurposed as a creation request) to the appropriate domain supervisor. The supervisor's worker generates the full action draft payload using the same LLM-backed pipeline it uses for modifications.

**Rationale**: The supervisor-worker already knows the domain schema and patient context. Re-using it avoids duplicating action-generation logic in the executor.

**Alternative considered**: Executor generates the action draft itself without touching a supervisor. Rejected — would duplicate domain-specific prompt logic and deviate from the established multi-agent boundary.

---

### 5. Frontend ChatPanel is a self-contained route, not a modal

**Decision**: ChatPanel is mounted at `/chat` as a full-page route in the React dashboard. It is accessible from a nav link. It does not share state with ActionFeed.

**Rationale**: Modals are hard to use for long conversations. A dedicated route allows deep-linking and avoids z-index/scroll conflicts. ActionFeed updates independently via its existing 10s polling.

## Risks / Trade-offs

- **LLM classification errors** → Mitigation: Clarification loop lets the caregiver correct wrong domain/patient assumptions before anything is written.
- **Staged rows accumulate** → Mitigation: Add a nightly cleanup job (or startup sweep) that marks `pending_approval` staged rows older than 24 h as `discarded`.
- **Supervisor returns a malformed draft** → Mitigation: Executor validates required fields (patient_id, domain, type, description) before staging; returns an error message to the chat if validation fails.
- **Caregiver approves a draft, then navigates away before ActionFeed polls** → Acceptable: ActionFeed picks it up within 10 s on next poll cycle.

## Open Questions

- Should the `/chat` endpoint support anonymous sessions (no auth) for demo purposes, or require the same auth header as other endpoints? *(Assume no auth for demo consistency with the rest of the stack.)*
- Should Modify produce a new staged row or update the existing one? *(Update in place — simpler, single approval card in UI.)*
