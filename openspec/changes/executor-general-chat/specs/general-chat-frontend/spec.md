## ADDED Requirements

### Requirement: ChatPanel renders a scrollable message thread
The ChatPanel component SHALL display all messages for the current session in chronological order. User messages SHALL be right-aligned. Agent messages SHALL be left-aligned. Each message SHALL show role, content, and timestamp. The thread SHALL auto-scroll to the latest message on each new reply.

#### Scenario: Messages render in order
- **WHEN** a session has 4 messages (2 user, 2 agent)
- **THEN** all 4 render in chronological order with correct alignment and timestamps

### Requirement: ChatPanel shows an intent badge on the first agent clarification message
The first agent message in a `clarifying` stage SHALL display a badge indicating the executor's classified intent (`Question` or `New Action`) and resolved domain (e.g., `Health`). If the stage is `answered` or `draft_ready`, no badge is shown on subsequent messages.

#### Scenario: Clarification badge displayed
- **WHEN** the executor returns a message with `stage: "clarifying"`, `intent: "create-action"`, `domain: "health"`
- **THEN** the message shows a badge "New Action · Health" above the message content

### Requirement: ChatPanel renders an inline draft action card when stage is draft_ready
When a chat message has `stage: "draft_ready"` and a non-null `draft_action_id`, the ChatPanel SHALL render a DraftActionCard below the agent message. The card SHALL display a summary of the draft (patient name, action type, description, scheduled time if present). It SHALL show three buttons: Approve, Modify, Discard.

#### Scenario: Draft card renders with controls
- **WHEN** an agent message arrives with `stage: "draft_ready"` and a valid `draft_action_id`
- **THEN** a DraftActionCard appears with the draft summary and Approve / Modify / Discard buttons

### Requirement: Approve button commits the draft and updates the card state
When the caregiver clicks Approve, the ChatPanel SHALL call `POST /chat/action/:draft_action_id/approve`. On success it SHALL replace the DraftActionCard with a confirmation message ("Action added to feed") and disable all three buttons. It SHALL NOT navigate away from the chat.

#### Scenario: Approve commits draft
- **WHEN** Approve is clicked
- **THEN** the API is called, the card shows "Action added to feed", and buttons are disabled

### Requirement: Discard button removes the staged draft and collapses the card
When the caregiver clicks Discard, the ChatPanel SHALL call `POST /chat/action/:draft_action_id/discard`. On success it SHALL replace the DraftActionCard with a neutral message ("Draft discarded") and disable all three buttons.

#### Scenario: Discard removes draft
- **WHEN** Discard is clicked
- **THEN** the API is called and the card shows "Draft discarded" with disabled buttons

### Requirement: Modify button opens an inline feedback input
When the caregiver clicks Modify, the DraftActionCard SHALL reveal a single-line text input and a Submit button beneath the existing summary. The caregiver types their feedback and clicks Submit. The ChatPanel SHALL call `POST /chat/action/:draft_action_id/modify` with `{ feedback }`. On success it SHALL append the executor's revised reply to the thread and update the DraftActionCard with the new draft summary in place.

#### Scenario: Modify submits feedback and shows revised draft
- **WHEN** the caregiver types "Change the time to 3pm" and clicks Submit
- **THEN** the modify API is called, the executor reply is appended to the thread, and the DraftActionCard updates in place with the revised draft

### Requirement: ChatPanel input bar sends messages and handles loading state
The ChatPanel SHALL have a fixed-bottom input bar with a text field and Send button. While awaiting the executor reply, the Send button SHALL be disabled and show a loading indicator. The input field SHALL be cleared on send. Messages SHALL be optimistically appended to the thread as a user message before the response arrives.

#### Scenario: Send disables input during loading
- **WHEN** the caregiver sends a message
- **THEN** the user message appears immediately, the Send button is disabled and shows a spinner, and it re-enables once the agent reply arrives

### Requirement: ChatPanel is accessible at /chat route in the dashboard
The dashboard router SHALL include a `/chat` route that renders ChatPanel. A nav link in the sidebar SHALL link to `/chat`. Session state SHALL be initialized from `GET /chat/history` on mount if a stored `session_id` exists in localStorage.

#### Scenario: Session restored from localStorage
- **WHEN** the caregiver navigates to /chat and a session_id exists in localStorage
- **THEN** the prior conversation history is fetched and rendered before the input bar is active
