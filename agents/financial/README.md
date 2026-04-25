# Financial Agents

This directory contains the **Financial Supervisor** and **Financial Worker** agents — a two-agent pipeline that handles all financial-related queries in the Autocare multi-agent system.

## Triggered by keywords

`financial`, `bill`, `payment`, `autopay`, `invoice`

---

## Financial Supervisor (`financial-supervisor`)

The supervisor is the domain coordinator. It receives a task from the Executor, stamps it with routing metadata, delegates it to the worker, and aggregates the worker result into a final `MockSupervisorResult` that is sent back to the Executor.

### Message flow

```
Executor  →  MockDomainTask  →  Supervisor  →  MockDomainTask  →  Worker
    ↑                                ↑                                 |
    └──── MockSupervisorResult ──────┘◄────── MockWorkerResult ────────┘
```

### Port

`8401`

---

## Financial Worker (`financial-worker`)

The worker performs the actual processing of the financial query. It receives a delegated `MockDomainTask` from the supervisor, processes it, and returns a `MockWorkerResult`.

### Port

`8402`

---

## Message schemas

**`MockDomainTask`** (Executor → Supervisor → Worker)

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | Unique request identifier |
| `domain` | `str` | Must be `"financial"` |
| `query` | `str` | Free-text financial query |
| `user_sender_address` | `str \| None` | Return address for chat replies |
| `metadata` | `dict \| None` | Routing context (supervisor stamps `financial_supervisor: forwarded`) |

**`MockWorkerResult`** (Worker → Supervisor)

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | Echoed from the task |
| `domain` | `str` | `"financial"` |
| `worker` | `str` | `"financial-worker"` |
| `result` | `str` | Processed result string |

**`MockSupervisorResult`** (Supervisor → Executor)

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | Echoed from the task |
| `domain` | `str` | `"financial"` |
| `supervisor` | `str` | `"financial-supervisor"` |
| `result` | `str` | Final human-readable result |

## Running

```
# In separate terminals:
python -m agents.financial.supervisor
python -m agents.financial.worker
```
