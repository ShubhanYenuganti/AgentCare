## ADDED Requirements

### Requirement: Executor classifies general-chat messages as question or create-action
Upon receiving a `/general-chat` request, the executor SHALL classify the user message into one of two intent classes: `question` or `create-action`. It SHALL use the full session message history as context for classification. It SHALL NOT route to the `modification`, `scheduling`, or `detection` paths from the general chat surface.

#### Scenario: Question intent classified
- **WHEN** the executor receives "What medications is Margaret currently taking?" via `/general-chat`
- **THEN** the executor classifies intent as `question` and proceeds to the question resolution path

#### Scenario: Create-action intent classified
- **WHEN** the executor receives "I need to set up a physiotherapy appointment for Robert next week"
- **THEN** the executor classifies intent as `create-action` and proceeds to the domain + patient resolution path

### Requirement: Executor resolves domain and patients for create-action intent
After classifying `create-action`, the executor SHALL identify the target domain (health, financial, grocery, scheduling) and all patients referenced in the message. It SHALL match patient names against the DB patient roster using fuzzy string matching. It SHALL produce a structured assumptions object: `{ intent, domain, patients: [{ id, name }] }`.

#### Scenario: Domain and patient resolved
- **WHEN** the message is "Schedule a dentist check-up for Margaret Chen next Tuesday"
- **THEN** assumptions object contains `{ intent: "create-action", domain: "health", patients: [{ id: "pat_001", name: "Margaret Chen" }] }`

#### Scenario: Ambiguous patient name triggers clarification
- **WHEN** the message references "Robert" and multiple patients named Robert exist
- **THEN** the executor enters the clarification stage asking which Robert the caregiver means

### Requirement: Executor runs multi-turn clarification loop before proceeding
After resolving assumptions, the executor SHALL compose a clarification message stating its understood intent, domain, and patient(s) and asking the caregiver to confirm. It SHALL return this message with `stage: "clarifying"`. On the next turn it SHALL re-evaluate the caregiver's reply to determine if assumptions are confirmed or need correction. It SHALL repeat until the caregiver confirms or the session is abandoned.

#### Scenario: Caregiver confirms assumptions
- **WHEN** the executor asks "I'll create a health action for Margaret Chen — is that right?" and the caregiver replies "Yes"
- **THEN** the executor transitions to `stage: "generating"` and dispatches to the domain supervisor

#### Scenario: Caregiver corrects an assumption
- **WHEN** the caregiver replies "Actually it's for Robert, not Margaret"
- **THEN** the executor updates the patient in its assumptions and asks for confirmation again

### Requirement: Executor dispatches confirmed create-action to the domain supervisor
Once assumptions are confirmed, the executor SHALL send a creation request to the domain supervisor for the resolved domain. It SHALL await the supervisor's draft action payload. It SHALL write the draft to `staged_actions` with status `pending_approval`. It SHALL return the draft summary to the chat with `stage: "draft_ready"` and `draft_action_id` set.

#### Scenario: Supervisor returns draft action
- **WHEN** the health supervisor returns a draft action payload for Margaret Chen's dentist appointment
- **THEN** a `staged_actions` row is created with `pending_approval`, and the executor reply contains `stage: "draft_ready"` and `draft_action_id`

#### Scenario: Supervisor returns invalid payload
- **WHEN** the supervisor returns a payload missing required fields (patient_id, domain, type, description)
- **THEN** the executor does NOT write a staged row and returns a chat message with `stage: "error"` describing the missing fields

### Requirement: Executor handles question intent with direct LLM answer
When the executor classifies intent as `question`, it SHALL skip domain supervisor dispatch. It SHALL fetch the relevant patient life graph from the DB if a patient is identified. It SHALL construct a context-aware LLM prompt and return the answer directly as `stage: "answered"`.

#### Scenario: Question answered with patient context
- **WHEN** intent is `question` and a patient is resolved
- **THEN** the executor fetches the patient life graph, builds a prompt, and returns a conversational answer with `stage: "answered"`

#### Scenario: Question answered without patient context
- **WHEN** intent is `question` and no patient is referenced
- **THEN** the executor answers from general caregiving knowledge with `stage: "answered"`

### Requirement: Executor /general-chat/revise regenerates draft with feedback
The executor SHALL expose `/general-chat/revise` accepting `{ original_draft, feedback, session_id }`. It SHALL send the original draft and feedback to the domain supervisor for the draft's domain. It SHALL return the revised draft payload. If the revised draft fails validation, it SHALL return a descriptive error.

#### Scenario: Revised draft incorporates feedback
- **WHEN** feedback is "Change the time to 3pm" and original draft has `start_time: "10:00"`
- **THEN** the revised draft returned by the supervisor has `start_time: "15:00"`
