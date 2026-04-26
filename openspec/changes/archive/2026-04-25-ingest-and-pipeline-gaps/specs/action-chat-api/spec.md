## ADDED Requirements

### Requirement: POST /actions/{id}/chat routes user message through executor pipeline
The endpoint SHALL accept `{ "message": str }`. It SHALL write the user message to `action_chat` (role=`user`) via `db.write_chat_message`. It SHALL then POST the message to `EXECUTOR_INTERNAL_URL/message` with the action context prepended (action_id, patient_id, domain, type). It SHALL return `{ "status": "queued", "chat_id": int }`. If the executor is not reachable, it SHALL return HTTP 502. If the action does not exist, it SHALL return 404.

#### Scenario: chat message is written and forwarded
- **WHEN** `POST /actions/act_001/chat` receives `{ "message": "Can you reschedule this?" }`
- **THEN** a user message row is written to `action_chat` and the message is forwarded to the executor `/message` endpoint with action context

#### Scenario: action not found returns 404
- **WHEN** `POST /actions/nonexistent/chat` is called
- **THEN** the endpoint returns HTTP 404

#### Scenario: executor unreachable returns 502
- **WHEN** the executor at `EXECUTOR_INTERNAL_URL` is not reachable
- **THEN** the endpoint returns HTTP 502 with `{ "error": "executor_unavailable" }`

### Requirement: GET /actions/{id}/chat-history returns ordered chat messages
The endpoint SHALL return all `action_chat` rows for the action ordered by `id ASC`. Each entry SHALL include `id`, `role`, `content`, `intent`, `created_at`. If the action does not exist, it SHALL return 404.

#### Scenario: chat history returns messages in order
- **WHEN** `GET /actions/act_001/chat-history` is called after two user messages and one agent reply
- **THEN** the response contains three rows in chronological order with `role` values `user`, `user`, `agent`
