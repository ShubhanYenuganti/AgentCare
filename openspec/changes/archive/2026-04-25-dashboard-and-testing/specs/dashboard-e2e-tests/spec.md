## ADDED Requirements

### Requirement: Action Feed E2E tests
The Playwright test suite SHALL include tests for the Action Feed view covering: initial load, urgency sort order, overdue banner display, chat panel open/send/history, and draft modal submit.

#### Scenario: Action Feed loads and sorts by urgency
- **WHEN** the Action Feed view is navigated to
- **THEN** actions are displayed with high-urgency cards first and overdue banners visible on overdue actions

#### Scenario: Chat panel send and receive
- **WHEN** a user opens the chat panel and sends a message
- **THEN** the message appears in the chat history within 5 seconds

### Requirement: Patient Roster E2E tests
The Playwright test suite SHALL include tests for patient selection, add patient (text), staged update confirmation, and update history tab.

#### Scenario: Patient detail loads on selection
- **WHEN** a user clicks a patient in the sidebar
- **THEN** the detail panel displays that patient's name and life graph summary within 2 seconds

### Requirement: Caregiver Management E2E tests
The Playwright test suite SHALL include tests for scheduling strip display, caregiver selection, schedule grid render, and confirm/decline flows.

#### Scenario: Confirm scheduling action
- **WHEN** a user clicks Confirm on an unconfirmed scheduling action
- **THEN** the action card updates to show `scheduling_status="confirmed"`

### Requirement: Org Dashboard E2E tests
The Playwright test suite SHALL include tests for org summary load, protocol panel render, and org profile edit.

#### Scenario: Org profile edit
- **WHEN** a user submits the org profile edit form
- **THEN** the summary panel refreshes with the updated org name
