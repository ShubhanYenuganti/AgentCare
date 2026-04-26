# Domain Modification and Question Pipelines

## Purpose

Defines how domain supervisors handle modification requests and question requests, including live-data branching, non-health modification guards, and supervisor risk-scoring reassessment.

## Requirements

### Requirement: Health modification live-data path
The health supervisor SHALL route modification requests through a live-data aware revision path: worker fetches fresh API data if `requires_live_api=true`, produces a revised draft, supervisor applies a review pass and optionally a retry pass, then returns `ModificationResult` with `changes_summary`.

#### Scenario: Modification with live API data
- **WHEN** a `ModificationRequest` arrives with fields that require live data
- **THEN** the supervisor sets `requires_live_api=true` on the `ModificationTask`, worker calls the relevant mock API, and the revised draft incorporates the fresh data

#### Scenario: Modification without live data
- **WHEN** a `ModificationRequest` can be resolved from the life graph snapshot alone
- **THEN** the supervisor sets `requires_live_api=false`, worker revises from snapshot, and supervisor returns the draft without an API call

### Requirement: Non-health modification guard
Appointment, grocery, and financial supervisors SHALL return a `ModificationResult` with `revised_draft="not_supported"` and `changes_summary="Modification not supported for this domain"` when receiving a `ModificationRequest`, without delegating to a worker.

#### Scenario: Non-health domain receives modification
- **WHEN** a `ModificationRequest` is sent to the appointment, grocery, or financial supervisor
- **THEN** the supervisor returns `ModificationResult(revised_draft="not_supported", changes_summary="Modification not supported for this domain")` immediately

### Requirement: Question live-API branching
All domain supervisors SHALL check freshness keywords in the question text and set `api_lookup_instruction` on the `QuestionTask` if live data is required. Workers SHALL call the relevant mock API when `api_lookup_instruction` is non-null and include the API response in their `QuestionApiResult`.

#### Scenario: Question requires fresh data
- **WHEN** a question contains freshness keywords (e.g., "current", "latest", "today")
- **THEN** the supervisor sets a non-null `api_lookup_instruction` on the `QuestionTask` and the worker calls the mock API before answering

#### Scenario: Question answerable from snapshot
- **WHEN** the question does not contain freshness keywords
- **THEN** the supervisor sets `api_lookup_instruction=None` and the worker answers from the life graph snapshot

### Requirement: Supervisor risk-scoring reassessment
All domain supervisors SHALL apply a single LLM risk-scoring pass after collecting worker drafts to reassess urgency framing, override urgency levels where warranted, and recalculate `review_by` dates before persisting actions.

#### Scenario: Urgency upgraded by risk scoring
- **WHEN** the LLM risk-scoring pass determines a draft warrants higher urgency than the worker assigned
- **THEN** the supervisor overwrites `urgency_level` and adjusts `review_by` accordingly before writing to DB
