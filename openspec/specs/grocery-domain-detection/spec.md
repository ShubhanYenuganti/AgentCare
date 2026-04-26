# Grocery Domain Detection

## Purpose

Defines the behavior of the grocery domain worker for detecting delivery staleness, dietary conflicts, and supply reorder needs.

## Requirements

### Requirement: Delivery staleness check
The grocery worker SHALL detect when the last grocery delivery is older than the configured staleness threshold (default 7 days) and generate a `type="grocery_reorder"` draft by calling the cart/order mock API.

#### Scenario: Delivery stale
- **WHEN** the most recent grocery delivery timestamp is more than 7 days ago
- **THEN** the worker calls `POST /mock/grocery/order` with the patient's staple list and generates an `ActionDraft` with `type="grocery_reorder"` and `urgency_level="medium"`

#### Scenario: Recent delivery
- **WHEN** the most recent grocery delivery is within 7 days
- **THEN** no reorder draft is generated

### Requirement: Dietary conflict detection
The grocery worker SHALL compare the patient's current grocery staples against their dietary restrictions and generate a `type="dietary_conflict_alert"` draft if a conflict is found.

#### Scenario: Conflict found
- **WHEN** a grocery staple item conflicts with a patient's documented dietary restriction
- **THEN** the worker generates an `ActionDraft` with `type="dietary_conflict_alert"` and `urgency_level="medium"` listing the conflicting items in `draft_content`

#### Scenario: No conflict
- **WHEN** no grocery staple conflicts with dietary restrictions
- **THEN** no dietary conflict draft is generated

### Requirement: Supply reorder check
The grocery worker SHALL detect when a tracked supply item's quantity drops below its reorder threshold and generate a `type="supply_reorder"` draft.

#### Scenario: Supply below threshold
- **WHEN** a supply item's recorded quantity is at or below its `reorder_threshold`
- **THEN** the worker generates an `ActionDraft` with `type="supply_reorder"` and `urgency_level="low"`
