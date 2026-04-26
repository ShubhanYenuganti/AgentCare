## 1. Database Schema

- [x] 1.1 Add `chat_sessions` table (id UUID PK, created_at) to schema and migrations
- [x] 1.2 Add `chat_messages` table (id, session_id FK, role, content, stage, intent_class, domain, patient_ids JSON, draft_action_id, created_at)
- [x] 1.3 Add `staged_actions` table (id UUID PK, session_id FK, draft_payload JSON, status enum pending_approval/discarded/committed, created_at)
- [x] 1.4 Add DB helper functions: `create_session`, `write_chat_message`, `get_session_messages`, `write_staged_action`, `get_staged_action`, `update_staged_action_status`, `commit_staged_to_action_history`

## 2. FastAPI Chat Router

- [x] 2.1 Create `api/routers/chat.py` with `POST /chat` endpoint (session creation + message write + executor dispatch)
- [x] 2.2 Implement `GET /chat/history` endpoint (session lookup + ordered message return)
- [x] 2.3 Implement `POST /chat/action/{draft_action_id}/approve` (copy staged payload to action_history, mark committed)
- [x] 2.4 Implement `POST /chat/action/{draft_action_id}/discard` (mark staged row discarded)
- [x] 2.5 Implement `POST /chat/action/{draft_action_id}/modify` (retrieve draft, forward to executor /general-chat/revise, update staged row)
- [x] 2.6 Register `chat` router in `main.py`

## 3. Executor General-Chat Pipeline

- [x] 3.1 Add `/general-chat` endpoint to the executor FastAPI app accepting `{ session_id, messages: [...] }`
- [x] 3.2 Implement intent classification step: LLM call that outputs `{ intent: "question" | "create-action", confidence }` from session history
- [x] 3.3 Implement domain + patient resolution step for `create-action`: LLM extraction → fuzzy DB patient match
- [x] 3.4 Implement clarification loop logic: compose assumption message, return `stage: "clarifying"`; on next turn re-evaluate caregiver reply to confirm or re-resolve
- [x] 3.5 Implement supervisor dispatch for confirmed `create-action`: send `QuestionTask` to appropriate domain supervisor, await draft payload
- [x] 3.6 Validate draft payload fields (patient_id, domain, type, description); return `stage: "error"` message if invalid
- [x] 3.7 On valid draft, call `write_staged_action` and return `{ stage: "draft_ready", draft_action_id, reply }`
- [x] 3.8 Implement question path: fuzzy-resolve patient if present, fetch life graph, LLM answer, return `stage: "answered"`
- [x] 3.9 Add `/general-chat/revise` endpoint: accept `{ original_draft, feedback, session_id }`, dispatch to domain supervisor, return revised payload
- [x] 3.10 Add `create-action` to the executor intent class enum; ensure it is unreachable from the `/message` (action-bound) path

## 4. Staged Action Cleanup

- [x] 4.1 Add startup sweep in `main.py` that sets `status = "discarded"` for all `staged_actions` rows older than 24 h with `status = "pending_approval"`

## 5. Frontend ChatPanel

- [x] 5.1 Create `dashboard/src/components/ChatPanel.tsx` with scrollable message thread (user right-aligned, agent left-aligned)
- [x] 5.2 Implement session init: on mount, read `session_id` from localStorage; if present call `GET /chat/history` and render history
- [x] 5.3 Implement fixed-bottom input bar with Send button; optimistic user message append; loading/disabled state while awaiting reply
- [x] 5.4 Implement intent badge rendering on first `clarifying` agent message (intent label + domain label)
- [x] 5.5 Create `DraftActionCard.tsx` component: renders draft summary (patient, type, description, schedule if present) + Approve / Modify / Discard buttons
- [x] 5.6 Wire Approve button to `POST /chat/action/:id/approve`; on success replace card with "Action added to feed" confirmation
- [x] 5.7 Wire Discard button to `POST /chat/action/:id/discard`; on success replace card with "Draft discarded"
- [x] 5.8 Wire Modify button to reveal inline feedback input + Submit; on Submit call `POST /chat/action/:id/modify`; append executor reply and update DraftActionCard in place
- [x] 5.9 Store `session_id` in localStorage after first message; clear on browser tab close is not required

## 6. Routing & Navigation

- [x] 6.1 Add `/chat` route to the React router in `App.tsx` rendering `ChatPanel`
- [x] 6.2 Add "Chat" nav link in the sidebar component pointing to `/chat`

## 7. Seed & Verification

- [ ] 7.1 Verify seed script still runs cleanly with new tables present (no FK violations)
- [ ] 7.2 Manually exercise happy-path flow end-to-end: question intent → answer; create-action intent → clarify → approve → ActionFeed update
- [ ] 7.3 Manually exercise Modify flow: draft → modify feedback → revised draft → approve
- [ ] 7.4 Manually exercise Discard flow: draft → discard → no action in feed

