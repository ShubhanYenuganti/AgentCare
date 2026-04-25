# Appointment Agents

This directory contains the **Appointment Supervisor** and **Appointment Worker** agents — a two-agent pipeline that handles all appointment-related queries in the Autocare multi-agent system.

## Triggered by keywords

`appointment`, `clinic`, `doctor`, `transport`, `visit`

---

## Appointment Supervisor (`appointment-supervisor`)

The supervisor is the domain coordinator. It receives a task from the Executor, stamps it with routing metadata, delegates it to the worker, and aggregates the worker result into a final `MockSupervisorResult` that is sent back to the Executor.

### Message flow

```
Executor  →  MockDomainTask  →  Supervisor  →  MockDomainTask  →  Worker
    ↑                                ↑                                 |
    └──── MockSupervisorResult ──────┘◄────── MockWorkerResult ────────┘
```

### Port

`8201`

---

## Appointment Worker (`appointment-worker`)

The worker performs the actual processing of the appointment query. It receives a delegated `MockDomainTask` from the supervisor, processes it, and returns a `MockWorkerResult`.

### Port

`8202`

---

## Message schemas

**`MockDomainTask`** (Executor → Supervisor → Worker)

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | Unique request identifier |
| `domain` | `str` | Must be `"appointment"` |
| `query` | `str` | Free-text appointment query |
| `user_sender_address` | `str \| None` | Return address for chat replies |
| `metadata` | `dict \| None` | Routing context (supervisor stamps `appointment_supervisor: forwarded`) |

**`MockWorkerResult`** (Worker → Supervisor)

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | Echoed from the task |
| `domain` | `str` | `"appointment"` |
| `worker` | `str` | `"appointment-worker"` |
| `result` | `str` | Processed result string |

**`MockSupervisorResult`** (Supervisor → Executor)

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | Echoed from the task |
| `domain` | `str` | `"appointment"` |
| `supervisor` | `str` | `"appointment-supervisor"` |
| `result` | `str` | Final human-readable result |

## Running

```bash
# In separate terminals:
python -m agents.appointment.supervisor
python -m agents.appointment.worker
```
