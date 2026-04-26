## MODIFIED Requirements

### Requirement: General query fallback
The executor SHALL handle queries that do not match detection, scheduling, modification, or question intents by fetching DB-backed patient context and generating a direct LLM answer. The executor SHALL also route general-chat surface messages through the two-step classification pipeline (`question` vs `create-action`) before applying this fallback, ensuring the fallback is only reached when neither intent class can be resolved with sufficient confidence.

#### Scenario: General query with patient context
- **WHEN** the executor classifies a query as a general question with a resolved patient ID
- **THEN** it fetches the patient life graph, constructs a context-aware prompt, and returns a conversational LLM response

#### Scenario: General query without patient context
- **WHEN** the executor classifies a query as a general question and no patient is referenced
- **THEN** the executor answers from general caregiving knowledge without fetching any patient data

#### Scenario: Low-confidence classification falls back to general query
- **WHEN** the executor cannot confidently classify a general-chat message as `question` or `create-action`
- **THEN** the executor treats it as a general question and returns a conversational LLM response

## ADDED Requirements

### Requirement: create-action intent class is recognized as a first-class executor intent
The executor SHALL recognize `create-action` as a valid intent class alongside `question`, `modification`, `scheduling`, and `detection`. This intent class SHALL only be triggered from the general-chat surface (`/general-chat`), never from the action-bound chat surface (`/actions/{id}/chat`). The executor SHALL dispatch `create-action` intent through the general-chat-executor-pipeline (domain resolution → clarification loop → supervisor dispatch → staging).

#### Scenario: create-action routed to general-chat pipeline
- **WHEN** the executor receives a `/general-chat` message classified as `create-action`
- **THEN** it routes to the clarification loop, not to the modification or detection pipeline

#### Scenario: create-action not triggered from action-bound chat
- **WHEN** a message arrives via `/actions/{id}/chat` and would otherwise classify as `create-action`
- **THEN** the executor routes it as a `modification` intent (existing action-bound path) instead
