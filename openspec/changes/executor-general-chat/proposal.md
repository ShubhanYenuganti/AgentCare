## Why

Caregivers currently have no way to ask freeform questions or create new care actions conversationally — every action must be authored through rigid forms. A general chat interface backed by the executor lets caregivers describe needs in natural language and either get an immediate answer or collaboratively draft a new action, dramatically reducing the friction of care coordination.

## What Changes

- **New**: `POST /chat` — a standalone chat endpoint (not action-bound) that accepts a free-text message and a conversation session, routes through the executor's classification pipeline, and streams back a response or draft
- **New**: `GET /chat/history` — retrieves the conversation history for a given session
- **New**: Executor classification step for `create-action` intent — separate from `modification` (which edits an existing action) and `question`
- **New**: Multi-turn clarification loop in the executor — after initial classification, the executor proposes its assumptions (intent, domain, patients) and asks the user to confirm before proceeding
- **New**: Action staging — when the executor produces a draft action, it is held in a transient staging state (not written to `action_history`) until the user explicitly approves
- **New**: Chatbot frontend panel with message thread, intent badge display, inline draft-action card with Approve / Discard / Modify controls
- **Modified**: `executor-intent-surface` — adds `create-action` as a first-class intent class alongside existing `question`, `modification`, `scheduling`, and `detection`

## Capabilities

### New Capabilities

- `general-chat-api`: Standalone REST endpoints (`/chat`, `/chat/history`) for session-scoped free-text conversation, decoupled from any existing action ID
- `general-chat-executor-pipeline`: Executor logic for the new conversational flow — intent classification (question vs. create-action), domain + patient resolution, multi-turn clarification loop, staging, approval/discard/modify branching
- `general-chat-frontend`: React chatbot panel supporting the full conversation flow including clarification bubbles, intent badge, inline draft action card, and Approve/Discard/Modify actions

### Modified Capabilities

- `executor-intent-surface`: Adds `create-action` intent class and clarification-loop handling to the existing intent routing surface

## Impact

- **Backend**: New FastAPI router (`api/routers/chat.py`); new DB table `chat_sessions` and `chat_messages`; executor agent gains `create-action` classification branch and staging logic
- **Frontend**: New `ChatPanel` React component mounted in the dashboard layout; uses existing `usePolling` / fetch patterns
- **No breaking changes**: existing `/actions/{id}/chat` endpoint is untouched; action feed write path is unchanged (staging is additive)
- **Dependencies**: No new third-party dependencies; reuses existing ASI:One client and supervisor message models
