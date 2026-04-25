# Scheduling Agent

The **Scheduling Agent** is a standalone domain agent in the Autocare multi-agent system. It handles all scheduling-related queries, such as finding caregiver availability, matching time slots, and coordinating scheduling options.

## What it does

- Receives a `MockDomainTask` (domain `"scheduling"`) forwarded by the Executor.
- Processes the scheduling query and returns a `MockSupervisorResult` back to the Executor with matched scheduling options.

## Triggered by keywords

`schedule`, `availability`, `caregiver`, `slot`

## Message flow

```
Executor  →  MockDomainTask  →  Scheduling Agent
    ↑                                   |
    └────────  MockSupervisorResult  ───┘
```

## Message schemas

**Input** — `MockDomainTask`

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | Unique request identifier |
| `domain` | `str` | Must be `"scheduling"` |
| `query` | `str` | Free-text scheduling query |
| `user_sender_address` | `str \| None` | Return address for chat replies |
| `metadata` | `dict \| None` | Optional context metadata |

**Output** — `MockSupervisorResult`

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | Echoed from the input task |
| `domain` | `str` | `"scheduling"` |
| `supervisor` | `str` | `"scheduling-agent"` |
| `result` | `str` | Human-readable scheduling outcome |

## Port

`8501`

## Running

```
python -m agents.scheduling.agent
```
