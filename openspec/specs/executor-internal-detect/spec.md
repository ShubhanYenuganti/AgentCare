# Spec: Executor Internal Detect

## Purpose

Defines the `POST /internal/detect` HTTP endpoint on the executor's internal FastAPI sub-app and the `run_detection` function that dispatches domain-specific detection requests with per-domain org context.

## Requirements

### Requirement: Executor exposes POST /internal/detect HTTP endpoint
The executor agent SHALL expose a `POST /internal/detect` endpoint (on a separate FastAPI sub-app, port 8001) that accepts `{ "patient_id": str, "trigger": str, "updated_domain": str | null }` and calls `run_detection()` on the uagents event loop. It SHALL return `{ "status": "triggered", "patient_id": str, "trigger": str }` on success.

#### Scenario: Detection triggered from FastAPI ingest route
- **WHEN** `POST /internal/detect` is called with `{ "patient_id": "pt_001", "trigger": "patient_create" }`
- **THEN** the endpoint returns HTTP 200 with `{ "status": "triggered", "patient_id": "pt_001", "trigger": "patient_create" }` and `run_detection()` is dispatched on the executor event loop

#### Scenario: Returns 503 when executor not yet running
- **WHEN** `POST /internal/detect` is called before the executor uagents event loop is ready
- **THEN** the endpoint returns HTTP 503 with `{ "detail": "Executor not ready" }`

#### Scenario: updated_domain is optional
- **WHEN** `POST /internal/detect` is called without `updated_domain` field
- **THEN** the endpoint accepts the request and passes `updated_domain=None` to `run_detection()`

### Requirement: run_detection injects domain-specific org context
`run_detection(patient_id, trigger, updated_domain)` SHALL use `ORG_CONTEXT_MAP` from `constants.py` to inject per-domain org context into each `OnDemandDetectionRequest`. It SHALL NOT send an empty dict as org_context.

#### Scenario: Health supervisor receives health protocol in org_context
- **WHEN** `run_detection("pt_001", "patient_create")` is called
- **THEN** the `OnDemandDetectionRequest` sent to the health supervisor has `org_context` containing `health_protocol` and `escalation_chain` keys

#### Scenario: Financial supervisor receives financial protocol in org_context
- **WHEN** `run_detection("pt_001", "patient_create")` is called
- **THEN** the `OnDemandDetectionRequest` sent to the financial supervisor has `org_context` containing `financial_protocol` and `escalation_lead` keys
