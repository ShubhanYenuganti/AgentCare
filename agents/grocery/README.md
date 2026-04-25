# Grocery Agents

This directory contains the **Grocery Supervisor** and **Grocery Worker** agents — a two-agent pipeline that handles all grocery-related queries in the Autocare multi-agent system.

## Triggered by keywords

`grocery`, `food`, `delivery`, `diet`, `instacart`

---

## Grocery Supervisor (`grocery-supervisor`)

The supervisor is the domain coordinator. It receives a task from the Executor, stamps it with routing metadata, delegates it to the worker, and aggregates the worker result into a final `MockSupervisorResult` that is sent back to the Executor.

### Message flow

```
Executor  →  MockDomainTask  →  Supervisor  →  MockDomainTask  →  Worker
    ↑                                ↑                                 |
    └──── MockSupervisorResult ──────┘◄────── MockWorkerResult ────────┘
```

### Port

`8301`

---

## Grocery Worker (`grocery-worker`)

The worker performs the actual processing of the grocery query. It receives a delegated `MockDomainTask` from the supervisor, processes it, and returns a `MockWorkerResult`.

### Port

`8302`

---

## Message schemas

**`MockDomainTask`** (Executor → Supervisor → Worker)

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | Unique request identifier |
| `domain` | `str` | Must be `"grocery"` |
| `query` | `str` | Free-text grocery query |
| `user_sender_address` | `str \| None` | Return address for chat replies |
| `metadata` | `dict \| None` | Routing context (supervisor stamps `grocery_supervisor: forwarded`) |

**`MockWorkerResult`** (Worker → Supervisor)

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | Echoed from the task |
| `domain` | `str` | `"grocery"` |
| `worker` | `str` | `"grocery-worker"` |
| `result` | `str` | Processed result string |

**`MockSupervisorResult`** (Supervisor → Executor)

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | Echoed from the task |
| `domain` | `str` | `"grocery"` |
| `supervisor` | `str` | `"grocery-supervisor"` |
| `result` | `str` | Final human-readable result |

## Running

```
# In separate terminals:
python -m agents.grocery.supervisor
python -m agents.grocery.worker
```
