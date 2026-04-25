# Health Agents

This directory contains the **Health Supervisor** and **Health Worker** agents — a two-agent pipeline that handles all health-related queries in the Autocare multi-agent system. Health is the highest-priority domain (priority score: 10).

## Triggered by keywords

`health`, `medication`, `pharmacy`, `refill`, `dose`

---

## Health Supervisor (`health-supervisor`)

The supervisor is the domain coordinator. It receives a task from the Executor, stamps it with routing metadata, delegates it to the worker, and aggregates the worker result into a final `MockSupervisorResult` that is sent back to the Executor.

### Message flow

```
Executor  →  MockDomainTask  →  Supervisor  →  MockDomainTask  →  Worker
    ↑                                ↑                                 |
    └──── MockSupervisorResult ──────┘◄────── MockWorkerResult ────────┘
```

### Port

`8101`

---

## Health Worker (`health-worker`)

The worker performs the actual processing of the health query. It receives a delegated `MockDomainTask` from the supervisor, processes it, and returns a `MockWorkerResult`.

### Port

`8102`

---

## Message schemas

**`MockDomainTask`** (Executor → Supervisor → Worker)

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | Unique request identifier |
| `domain` | `str` | Must be `"health"` |
| `query` | `str` | Free-text health query |
| `user_sender_address` | `str \| None` | Return address for chat replies |
| `metadata` | `dict \| None` | Routing context (supervisor stamps `health_supervisor: forwarded`) |

**`MockWorkerResult`** (Worker → Supervisor)

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | Echoed from the task |
| `domain` | `str` | `"health"` |
| `worker` | `str` | `"health-worker"` |
| `result` | `str` | Processed result string |

**`MockSupervisorResult`** (Supervisor → Executor)

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | Echoed from the task |
| `domain` | `str` | `"health"` |
| `supervisor` | `str` | `"health-supervisor"` |
| `result` | `str` | Final human-readable result |

## Running

```
# In separate terminals:
python -m agents.health.supervisor
python -m agents.health.worker
```
