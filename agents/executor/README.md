# Executor Agent

The **Executor** is the central orchestrator of the Autocare multi-agent system. It is the single entry point for all incoming queries — whether from a REST API call or from an Agentverse chat session.

## What it does

- Accepts free-text queries via:
  - `POST /message` (REST endpoint, body: `{"content": "<query>"}`)
  - Agentverse chat messages (via the `executor-chat` protocol)
- Classifies each query into one of five domains using keyword matching:

  | Domain | Keywords |
  |---|---|
  | `health` | health, medication, pharmacy, refill, dose |
  | `appointment` | appointment, clinic, doctor, transport, visit |
  | `grocery` | grocery, food, delivery, diet, instacart |
  | `financial` | financial, bill, payment, autopay, invoice |
  | `scheduling` | schedule, availability, caregiver, slot |

- Routes a `MockDomainTask` to the appropriate domain supervisor.
- Tracks pending requests in memory via `request_state`.
- Receives a `MockSupervisorResult` from the supervisor and returns the final answer to the caller.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check — returns `{"status": "ok healthy"}` |
| `POST` | `/message` | Submit a free-text query for routing |

## Message flow

```
User / API  →  Executor  →  Domain Supervisor  →  Domain Worker
                  ↑                                      |
                  └──────────  MockSupervisorResult  ────┘
```

## Port

`8001`

## Protocols

- `executor-chat` — handles `ChatMessage` / `ChatAcknowledgement` from Agentverse

## Running

```
python -m agents.executor.agent
```
