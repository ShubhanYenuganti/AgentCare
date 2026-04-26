# Health Domain Detection

## Purpose

Defines the behavior of the health domain worker for detecting medication refill needs, missed dose follow-ups, drug interactions via OpenFDA, and active drug recalls.

## Requirements

### Requirement: Refill due check
The health worker SHALL detect when a medication's next refill date is within the configured window (default 7 days) and generate a draft action with `type="medication_refill"`.

#### Scenario: Refill within window
- **WHEN** a patient's medication has `next_refill_date` within 7 days from today
- **THEN** the worker generates an `ActionDraft` with `type="medication_refill"`, `urgency_level="high"` if within 3 days else `"medium"`, and `review_by` set to the refill date

#### Scenario: Refill not due
- **WHEN** a patient's medication has `next_refill_date` more than 7 days away
- **THEN** the worker does not generate a refill draft for that medication

### Requirement: Missed dose with worsening condition
The health worker SHALL detect when a missed dose is recorded alongside a worsening symptom note within the past 48 hours and generate a `type="missed_dose_followup"` draft.

#### Scenario: Missed dose and worsening note present
- **WHEN** a medication has `last_taken` more than its dose interval ago AND a caregiver note within 48 hours contains a worsening keyword
- **THEN** the worker generates an `ActionDraft` with `type="missed_dose_followup"` and `urgency_level="high"`

#### Scenario: Missed dose without worsening
- **WHEN** a medication has `last_taken` more than its dose interval ago but no recent worsening note exists
- **THEN** the worker does not generate a missed_dose_followup draft (refill check still applies independently)

### Requirement: OpenFDA drug interaction check
The health worker SHALL call the OpenFDA drug interaction API for each patient with two or more active medications and generate a `type="drug_interaction_alert"` draft if an interaction is flagged.

#### Scenario: Interaction found
- **WHEN** the OpenFDA API returns an interaction record for the patient's active medications
- **THEN** the worker generates an `ActionDraft` with `type="drug_interaction_alert"`, `urgency_level="high"`, and `draft_content` summarizing the flagged interaction

#### Scenario: OpenFDA API unavailable
- **WHEN** the OpenFDA API call times out or returns a non-200 response
- **THEN** the worker logs a warning, skips the interaction check, and continues detection without generating a draft

### Requirement: OpenFDA recall check
The health worker SHALL call the OpenFDA drug recall API for each active medication and generate a `type="drug_recall_alert"` draft if an active recall is found.

#### Scenario: Recall found
- **WHEN** the OpenFDA recall endpoint returns an active recall for a patient's medication
- **THEN** the worker generates an `ActionDraft` with `type="drug_recall_alert"` and `urgency_level="high"`

#### Scenario: No recall
- **WHEN** the OpenFDA recall endpoint returns no active recalls
- **THEN** no recall draft is generated for that medication
