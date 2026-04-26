# Dashboard Org View

## Purpose

Defines the behavior of the Org Dashboard view, including the org summary panel, protocol panels, metrics cards, and org profile editor.

## Requirements

### Requirement: Org summary panel
The Org Dashboard view SHALL display a summary panel with org name, protocol count, active caregiver count, and total patient count from `GET /org`.

#### Scenario: Org summary loaded
- **WHEN** the Org Dashboard view loads
- **THEN** the summary panel displays org name and counts fetched from `GET /org`

### Requirement: Protocol panels
The Org Dashboard SHALL render a panel for each protocol in the org profile with its name, description, and applicable domain.

#### Scenario: Protocols listed
- **WHEN** the org profile contains protocols
- **THEN** each protocol is displayed in its own card with name, description, and domain tag

### Requirement: Org metrics cards
The Org Dashboard SHALL render metric cards for: total pending actions, total overdue actions, completion rate (last 30 days), and average urgency score.

#### Scenario: Metrics displayed
- **WHEN** the Org Dashboard view loads
- **THEN** four metric cards are rendered with values derived from the actions data

### Requirement: Org profile editor
The Org Dashboard SHALL include an "Edit Org Profile" form that submits updates via `PUT /org`.

#### Scenario: Org profile updated
- **WHEN** a user submits the edit form
- **THEN** a `PUT /org` request is sent and the summary panel refreshes with the updated values
