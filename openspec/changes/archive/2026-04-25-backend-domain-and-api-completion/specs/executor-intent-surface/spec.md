## ADDED Requirements

### Requirement: Onboarding intent handling
The executor SHALL detect onboarding intent from new-user queries (no patient context, no action context) and respond with a guided onboarding message directing the user to ingest a patient record.

#### Scenario: Onboarding query detected
- **WHEN** the executor receives a query with no patient ID, no action ID, and no recognizable patient name
- **THEN** the executor returns a conversational onboarding message prompting the user to provide patient information via `/ingest/text` or `/ingest/file`

### Requirement: Scheduling query intent handling
The executor SHALL route scheduling-intent queries to the scheduling agent using the `SchedulingQuery` message model and await `SchedulingOptions` before replying to the user.

#### Scenario: Scheduling query routed
- **WHEN** the executor classifies intent as `"scheduling"` and resolves a patient and action ID
- **THEN** it sends a `SchedulingQuery` to the scheduling agent and relays the resulting options list to the user conversationally

### Requirement: Action-bound modification and question handling
The executor SHALL resolve the action ID from the `[Action context]` prefix injected by the chat endpoint and route the query as a modification or question to the appropriate domain supervisor based on the action's domain.

#### Scenario: Action-bound question
- **WHEN** the executor receives a message with an `action_id` context prefix and classifies intent as `"question"`
- **THEN** it sends a `QuestionRequest` to the domain supervisor for the action's domain and returns the `QuestionAnswer` conversationally

#### Scenario: Action-bound modification
- **WHEN** the executor receives a message with an `action_id` context prefix and classifies intent as `"modification"`
- **THEN** it sends a `ModificationRequest` to the health supervisor and returns the `ModificationResult` conversationally

### Requirement: General query fallback
The executor SHALL handle queries that do not match detection, scheduling, modification, or question intents by fetching DB-backed patient context and generating a direct LLM answer.

#### Scenario: General query with patient context
- **WHEN** the executor classifies a query as a general question with a resolved patient ID
- **THEN** it fetches the patient life graph, constructs a context-aware prompt, and returns a conversational LLM response
