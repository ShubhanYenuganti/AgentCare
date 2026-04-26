## ADDED Requirements

### Requirement: POST /chat initiates or continues a conversation session
The endpoint SHALL accept `{ "session_id": str | null, "message": str }`. If `session_id` is null, it SHALL create a new `chat_sessions` row and return a new UUID. It SHALL write the user message to `chat_messages` (role=`user`). It SHALL forward the full session context (all prior messages + new message) to the executor `/general-chat` internal endpoint. It SHALL write the executor's reply to `chat_messages` (role=`agent`) and return `{ "session_id": str, "reply": str, "stage": str, "draft_action_id": str | null }`. If the executor is unreachable, it SHALL return HTTP 502.

#### Scenario: New session is created
- **WHEN** `POST /chat` is called with `session_id: null` and `message: "I need to schedule a physiotherapy appointment for Margaret"`
- **THEN** a new `chat_sessions` row is created, a new `chat_messages` user row is written, the executor is called, and the response contains a fresh `session_id` and the executor's clarification reply

#### Scenario: Existing session continues
- **WHEN** `POST /chat` is called with a valid `session_id` and a follow-up message
- **THEN** all prior messages for that session are included in the executor context and the reply is written to the existing session

#### Scenario: Executor unreachable returns 502
- **WHEN** the executor at `EXECUTOR_INTERNAL_URL` is not reachable
- **THEN** the endpoint returns HTTP 502 with `{ "error": "executor_unavailable" }`

### Requirement: GET /chat/history returns ordered messages for a session
The endpoint SHALL accept `session_id` as a query parameter. It SHALL return all `chat_messages` rows for that session ordered by `id ASC`. Each entry SHALL include `id`, `role`, `content`, `stage`, `draft_action_id`, `created_at`. If the session does not exist, it SHALL return HTTP 404.

#### Scenario: History returns messages in order
- **WHEN** `GET /chat/history?session_id=<id>` is called after three turns
- **THEN** six rows are returned (3 user + 3 agent) in chronological order

#### Scenario: Unknown session returns 404
- **WHEN** `GET /chat/history?session_id=nonexistent` is called
- **THEN** the endpoint returns HTTP 404

### Requirement: POST /chat/action/:draft_action_id/approve commits a staged draft
The endpoint SHALL accept `draft_action_id`. It SHALL look up the matching `staged_actions` row in `pending_approval` status. It SHALL copy the `draft_payload` into `action_history` as a new action row. It SHALL mark the staged row `committed`. It SHALL return `{ "action_id": str }`. If the draft does not exist or is not `pending_approval`, it SHALL return HTTP 404.

#### Scenario: Draft is approved and appears in action feed
- **WHEN** `POST /chat/action/<draft_id>/approve` is called
- **THEN** a new row appears in `action_history` with data from `draft_payload` and the staged row is marked `committed`

### Requirement: POST /chat/action/:draft_action_id/discard removes a staged draft
The endpoint SHALL accept `draft_action_id`. It SHALL mark the matching `staged_actions` row as `discarded`. It SHALL NOT write anything to `action_history`. It SHALL return HTTP 200.

#### Scenario: Discarded draft does not appear in action feed
- **WHEN** `POST /chat/action/<draft_id>/discard` is called
- **THEN** the staged row status is `discarded` and no row exists in `action_history` for this draft

### Requirement: POST /chat/action/:draft_action_id/modify re-routes to the executor with feedback
The endpoint SHALL accept `{ "feedback": str }`. It SHALL retrieve the current `draft_payload` from the staged row. It SHALL POST `{ "original_draft": <payload>, "feedback": str, "session_id": str }` to the executor `/general-chat/revise` internal endpoint. It SHALL update the `staged_actions` row with the revised `draft_payload` returned by the executor. It SHALL write the executor's reply message to `chat_messages`. It SHALL return `{ "reply": str, "draft_action_id": str }`.

#### Scenario: Modify produces a revised draft
- **WHEN** `POST /chat/action/<draft_id>/modify` is called with `{ "feedback": "Change the time to 3pm instead" }`
- **THEN** the executor receives the original draft and feedback, returns a revised payload, and the staged row is updated in place
