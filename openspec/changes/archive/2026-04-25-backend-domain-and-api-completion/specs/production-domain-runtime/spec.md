## ADDED Requirements

### Requirement: Cross-domain modification guard
Appointment, grocery, and financial domain supervisors SHALL reject `ModificationRequest` messages and return a `ModificationResult` indicating the domain does not support modification, without delegating to a worker.

#### Scenario: Non-health modification rejected
- **WHEN** the appointment, grocery, or financial supervisor receives a `ModificationRequest`
- **THEN** it returns `ModificationResult(revised_draft="not_supported", changes_summary="Modification not supported for this domain")` without calling any worker

### Requirement: Q&A support across all domains
All four domain supervisors SHALL support `QuestionRequest` messages and delegate to a domain worker which optionally calls a live mock API based on the `api_lookup_instruction` field.

#### Scenario: Question answered from snapshot
- **WHEN** a `QuestionRequest` arrives with `api_lookup_instruction=None`
- **THEN** the supervisor delegates to the worker, worker answers from life graph snapshot, supervisor returns `QuestionAnswer`

#### Scenario: Question answered with live API
- **WHEN** a `QuestionRequest` arrives with a non-null `api_lookup_instruction`
- **THEN** the worker calls the specified mock API and incorporates its response into the answer
