# Dashboard Action Feed

## Purpose

Defines the behavior of the Action Feed view in the dashboard, including action display, ActionCard variants, overdue/tier banners, the ActionChatPanel slide-over, and the DraftModal for draft modifications.

## Requirements

### Requirement: Action Feed view
The dashboard SHALL render an Action Feed view listing all pending actions sorted by urgency rank, with each action displayed as a stateful `ActionCard`.

#### Scenario: Actions displayed by rank
- **WHEN** the Action Feed view loads
- **THEN** actions are fetched from `GET /actions?sort=rank` and rendered as `ActionCard` components in urgency order

### Requirement: ActionCard variants
`ActionCard` SHALL render three variants based on domain and action type: health-modify (shows modify button), non-health Q&A (shows ask button), and scheduling (shows scheduling deep-link button).

#### Scenario: Health modify card
- **WHEN** an action has `domain="health"` and a non-null `draft_content`
- **THEN** the card renders a "Modify Draft" button that opens `DraftModal` and an "Ask" button that opens `ActionChatPanel`

#### Scenario: Scheduling card deep-link
- **WHEN** an action has a non-null `manual_action_type`
- **THEN** the card renders a "View Scheduling" button that navigates to the Caregiver Management view with that action pre-selected

### Requirement: Overdue and tier banners
`ActionCard` SHALL display an "OVERDUE" banner for actions where `is_overdue=true` and a tier banner reflecting `urgency_level` using the spec color scheme (high=red, medium=amber, low=green).

#### Scenario: Overdue banner visible
- **WHEN** an action has `is_overdue=true`
- **THEN** the card displays a red "OVERDUE" banner

### Requirement: ActionChatPanel
The dashboard SHALL include an `ActionChatPanel` slide-over that sends messages to `POST /actions/{id}/chat` and polls `GET /actions/{id}/chat-history` every 3 seconds while open.

#### Scenario: Message sent and history polled
- **WHEN** a user types and sends a message in ActionChatPanel
- **THEN** the message is posted to the chat endpoint and the history panel updates within 3 seconds

### Requirement: DraftModal
`DraftModal` SHALL display the current `draft_content` for an action, allow inline editing, and submit changes via `PATCH /actions/{id}` with a `modification_instruction` and `idempotency_key`.

#### Scenario: Draft modification submitted
- **WHEN** a user edits the draft and clicks "Submit"
- **THEN** a PATCH request is sent with `modification_instruction` and a fresh `idempotency_key`, and the card reflects `modification_in_progress=true`
