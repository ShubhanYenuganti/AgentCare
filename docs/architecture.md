# MACOS Architecture

## Overview

MACOS is a 3-tier multi-agent care operations system built on the Fetch.ai uAgents framework with a FastAPI REST layer and a React dashboard.

```
ASI:One / Dashboard
        │
        ▼
   Executor Agent          ← Intent classifier + orchestrator
   (port 8001)
   ┌──────────────────────────────────────────┐
   │ Intent routing → question/modification/  │
   │   scheduling/detection                   │
   │ Expiration loop (every 15 min)           │
   └──────────────┬───────────────────────────┘
                  │ fan-out
         ┌────────┼──────────────┐
         ▼        ▼              ▼
    Health      Appt.        Grocery    Financial
   Supervisor  Supervisor   Supervisor  Supervisor
         │        │              │          │
         ▼        ▼              ▼          ▼
    Health      Appt.        Grocery    Financial
    Worker      Worker       Worker      Worker
         │                              Scheduling
         └──────────────────────────────  Agent
                                       (port 8009)
```

## Internal Detect Pipeline

When a patient record changes (via `/ingest/text`, `/ingest/file`, or `/patients/{id}/update/{uid}/confirm`), the FastAPI router calls:

```
POST /internal/detect
  trigger: "patient_create" | "patient_update"
  patient_id: str
  updated_domain: str | null  ← domain hint for targeted fan-out
```

The Executor's `internal_detect` endpoint:
1. Calls `_detection_domains_for_trigger(trigger, updated_fields, domain_hint)` to determine target domains.
2. Builds an `OnDemandDetectionRequest` per domain with the patient's life graph snapshot.
3. Sends requests to each domain supervisor in parallel.
4. Collects `WorkerResult` messages and writes `ActionDraft` records to `action_history`.

Fan-out rules:
- `patient_create` → all 4 domains (health, appointment, grocery, financial)
- `patient_update` with `updated_domain=health` → health only
- `patient_update` with no domain hint → all 4 domains

## Patient Update Staging

```
Dashboard → POST /patients/{id}/update
               │
               ▼ LLM classifies update
           proposed_changes stored in DB (status=pending)
               │
               ▼ Dashboard shows proposed changes
Dashboard → POST /patients/{id}/update/{uid}/confirm
               │
               ▼ apply_patient_update() writes to patient life graph
               │
               ▼ _trigger_detect(patient_id, "patient_update", domain)
```

State machine:
```
idle → submitting → awaiting_confirmation → confirmed | cancelled
```

## Scheduling Lifecycle

```
User query ("schedule a nurse visit")
        │
        ▼ Executor classifies as "scheduling"
Scheduling Agent:
  1. Queries available caregiver slots
  2. Sends options list to ASI:One/dashboard
  3. User sends numeric selection or "cancel"
  4. Scheduling Agent → update action:
       scheduling_status: "pending_approval" → "unconfirmed"
       assigned_caregiver: set

Dashboard → POST /scheduling/{id}/confirm
       scheduling_status: "unconfirmed" → "confirmed"
       completed: 1

Dashboard → POST /scheduling/{id}/decline
       scheduling_status: "unconfirmed" → "pending_approval"
       assigned_caregiver: cleared
       escalation notification written
```

## API Payload Contracts

### Action
```json
{
  "action_id": "act_abc123",
  "patient_id": "pt_001",
  "patient_name": "Margaret Chen",
  "domain": "health",
  "type": "medication_refill",
  "description": "Lisinopril refill due within 3 days",
  "urgency_level": "tier_2",
  "urgency_score": 2.5,
  "review_by": "2026-04-27T12:00:00Z",
  "is_overdue": 0,
  "completed": 0,
  "draft_content": "Caregiver should contact CVS Mission St...",
  "modification_in_progress": 0,
  "idempotency_key": null,
  "manual_action_type": null,
  "scheduling_status": null,
  "assigned_caregiver": null
}
```

### Patient (enriched)
```json
{
  "patient_id": "pt_001",
  "name": "Margaret Chen",
  "age": 72,
  "address": "123 Oak St, SF",
  "active": 1,
  "life_graph_json": { "health": {...}, "appointments": [...], "grocery": {...}, "financial": {...} },
  "pending_action_count": 3,
  "overdue_action_count": 1,
  "highest_urgency_level": "tier_1"
}
```

### Scheduling status values
| Value | Meaning |
|-------|---------|
| `pending_approval` | Action created, awaiting caregiver assignment |
| `unconfirmed` | Caregiver assigned, awaiting human confirmation |
| `confirmed` | Confirmed and completed |
| `cancelled` | Cancelled by user or system |

## Expiration Loop

Runs every 15 minutes on the Executor:
1. `get_overdue_actions()` — queries `action_history` where `review_by < now()` and `completed=0`.
2. `mark_action_overdue(action_id)` — sets `is_overdue=1`, `urgency_level="tier_0"`.
3. For each channel in `("dashboard", "asi_one")`:
   - `has_been_notified(action_id, channel)` — dedup check via `expiration_notifications` table.
   - If not notified: `write_notification()` + `log_expiration_notification()`.

Dedup guarantee: each `(action_id, channel)` pair is written exactly once.
