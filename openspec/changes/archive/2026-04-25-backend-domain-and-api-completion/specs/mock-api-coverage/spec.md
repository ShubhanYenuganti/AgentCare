## ADDED Requirements

### Requirement: Mock route stable response envelopes
All mock API endpoints used by detection and approval flows SHALL return stable response envelopes matching the spec snapshots. The Amazon reorder response SHALL include `order_id`, `status`, and `estimated_delivery` fields.

#### Scenario: Amazon reorder response shape
- **WHEN** `POST /mock/grocery/order` is called with a valid payload
- **THEN** the response includes `order_id`, `status`, and `estimated_delivery` fields

#### Scenario: Caregiver availability sort order
- **WHEN** `GET /mock/caregivers/available` is called
- **THEN** results are sorted: assigned caregiver first, then by start time; fallback to next 3 business days if no slots today

### Requirement: Mock endpoint coverage tests
Each mock endpoint used by detection and approval flows SHALL have at least one pytest test asserting the stable response envelope shape.

#### Scenario: Coverage test passes for each mock endpoint
- **WHEN** the mock API coverage test suite runs
- **THEN** all tests pass and assert non-empty response bodies with expected top-level fields
