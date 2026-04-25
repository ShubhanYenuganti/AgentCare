# MACOS — Implementation Runbook (Sprint 1 Complete + ASI:One Live)

## 1) Current implementation status

Sprint 1 scaffold is complete and the full ASI:One ↔ executor communication path is
validated end-to-end. All 10 agents boot, route messages correctly, and the chat
round-trip through ASI:One is confirmed working.

The current codebase is **scaffold-level** — domain business logic (LLM detection,
modification pipeline, live API calls) is not yet implemented. That is Sprint 2+.

Primary spec: `MACOS_build_spec_v7_final.md`.
OpenSpec tracking: `openspec/changes/implement-sprint-1-foundation/`.

---

## 2) Architecture (how it works)

### 2.1 Multi-agent topology

Ten uAgents processes, all started by `agents/run_all.py`:

```
ASI:One ──mailbox──▶ Executor ──direct──▶ Domain Supervisor ──direct──▶ Domain Worker
                         ▲                        │                           │
                         └────────────────────────┴───────────────────────────┘
                                    (direct local HTTP replies)
```

**Executor** (`agents/executor/agent.py`, port 8001)
- Single external entry point for ASI:One chat and REST calls.
- Exposes `GET /health`, `POST /message`, `GET /mailbox-debug`.
- Classifies free-text by keyword (`DOMAIN_KEYWORDS`) → routes `MockDomainTask` to
  the correct domain supervisor.
- Tracks in-flight requests in `request_state` (in-memory, keyed by `request_id`).
- Receives `MockSupervisorResult` and sends the final `ChatMessage` reply to ASI:One.
- Has `mailbox=True` — this is the **only** agent that needs the Agentverse mailbox,
  because it is the sole inbound channel from ASI:One.

**Domain supervisors/workers** (ports 8101–8402)
- Health: `agents/health/supervisor.py` + `agents/health/worker.py`
- Appointment: `agents/appointment/`
- Grocery: `agents/grocery/`
- Financial: `agents/financial/`
- All have `mailbox=True` (kept for Agentverse Inspector visibility and future
  cross-environment use) but route internally via `LocalFirstResolver` (direct HTTP).
- Supervisor: receives `MockDomainTask`, forwards to worker, collects `MockWorkerResult`,
  returns `MockSupervisorResult` to executor.
- Worker: receives task, returns deterministic mock result. Sprint 2 replaces this
  with real LLM + live API calls.

**Scheduling agent** (`agents/scheduling/agent.py`, port 8501)
- Handles `MockDomainTask` with `domain=scheduling` directly (no worker).

**Stack runner** (`agents/run_all.py`)
- Spawns all 10 agents as subprocesses.
- Validates `SQLITE_DB_PATH`, `EXECUTOR_INTERNAL_URL`, `MOCK_API_BASE` at startup.
- Graceful Ctrl+C shutdown.

### 2.2 Routing: LocalFirstResolver (critical for latency)

All agents use `resolve=LocalFirstResolver()` (defined in `agents/shared/config.py`).

**Why this matters:** Without it, every agent-to-agent `ctx.send()` makes a full
round-trip through the Agentverse cloud (almanac lookup → mailbox submit → target
polls every 1 s). With 4 hops in the pipeline, this compounds to 30–120 s of pure
infrastructure latency before any LLM call is even made.

`LocalFirstResolver` intercepts any `ctx.send()` to a known stack address and routes
it directly to `http://localhost:{port}/submit` instead. The Agentverse mailbox is
only used for the executor's **inbound** path (ASI:One → executor).

```
Hop                     Before              After
─────────────────────────────────────────────────
Executor → Supervisor   5–30 s mailbox      < 5 ms direct
Supervisor → Worker     5–30 s mailbox      < 5 ms direct
Worker → Supervisor     5–30 s mailbox      < 5 ms direct
Supervisor → Executor   5–30 s mailbox      < 5 ms direct
ASI:One → Executor      1–5 s  mailbox      unchanged (still mailbox)
Executor → ASI:One      1–5 s  mailbox      unchanged
```

For Sprint 2 with LLM calls, total per-query latency ≈ LLM call time (5–30 s each)
rather than being dominated by infrastructure.

**Do not remove `mailbox=True` from supervisors/workers.** The mailbox registration
keeps them visible and addressable in the Agentverse almanac. `LocalFirstResolver`
simply short-circuits the routing for local addresses; it falls back to `GlobalResolver`
for any unknown address (e.g. the ASI:One platform agent for reply delivery).

### 2.3 ASI:One ↔ Executor chat protocol

The executor uses `uagents_core.contrib.protocols.chat` (`AgentChatProtocol v0.3.0`).

**Critical implementation details learned during integration:**

1. **`allow_unverified=True` on both chat handlers is required.**
   ASI:One sends `ChatMessage` from a user-class address. Without this flag, uagents
   routes the message through `_signed_message_handlers`, which requires a verified
   agent-to-agent signature. User-address messages are silently rejected with an
   `ErrorMessage` sent back to ASI:One and zero log output — this is the canonical
   "silent failure" mode. Both handlers must be declared as:
   ```python
   @chat_proto.on_message(ChatMessage, allow_unverified=True)
   @chat_proto.on_message(ChatAcknowledgement, allow_unverified=True)
   ```

2. **`executor.include(chat_proto, publish_manifest=True)` must be called after
   defining all `@chat_proto.on_message` handlers.** The protocol is locked to the
   spec on construction; handlers added after `include()` are ignored.

3. **The correct ASI:One entry point is Agent Profile → "Chat with Agent".**
   The Agentverse Agent Inspector has its own embedded chat UI that connects directly
   to the agent's local port — this does NOT go through the mailbox and silently fails
   for locally-running agents. The flow that actually works:
   - Agentverse Agent Inspector → **Connect** → **Select Mailbox**
   - Then: Inspector → **Go to Agent Profile** → **Chat with Agent** (opens asi1.ai)
   - Messages sent from asi1.ai travel through the Agentverse mailbox → executor polls
     and receives them.

4. **Reply delivery uses the sender address from the envelope.** The executor stores
   `user_sender_address` in `PendingRequest` and sends the final `ChatMessage` back
   to that address when the pipeline completes. This address must be resolvable in the
   Agentverse almanac. The ASI:One platform agent IS registered, so replies succeed.
   One-shot/ephemeral test agents (like `test_chat_direct.py`) will log
   `Unable to resolve destination endpoint` for the reply — this is expected and benign.

5. **Immediate acknowledgement is sent before the pipeline runs.** The chat handler
   sends `"Processing your request…"` to ASI:One before invoking `_route_query()`.
   This gives the user instant feedback while the multi-hop pipeline + LLM calls
   complete in the background.

### 2.4 Mailbox diagnostics (executor-only endpoints)

The executor exposes two diagnostic tools useful during development:

- `GET http://localhost:8001/mailbox-debug`
  Polls the Agentverse mailbox API directly and returns the raw queue state. Use this
  immediately after sending from ASI:One to determine whether the message was queued
  at all. `item_count=0` after an ASI:One send means ASI:One is not submitting to the
  mailbox (wrong entry point — see section 2.3 point 3 above).

- `MAILBOX-DIAG` log lines every 20 s
  Periodic background poll showing `status=`, `items=`, and `error=`. If `status=404`
  appears, the Agentverse mailbox was never created for this agent (re-do Connect →
  Select Mailbox in the Inspector). If `status=200 items=0` persists indefinitely, the
  executor is reachable but no messages are being submitted.

The 20-second diagnostic interval can be removed once the stack is stable in
production — it adds unnecessary Agentverse API calls.

### 2.5 Almanac registration state

The executor's Agentverse registration (as of Sprint 1 completion):

```
address:   agent1qgs7zw0ce49c5k626tf8cag5wcjan7hhrpeguwlg836kkyjr69ypuwhms84
type:      mailbox
endpoint:  https://agentverse.ai/v2/agents/mailbox/submit
protocols: AgentChatProtocol (30a801ed...), executor internal (d9264ccd...)
expiry:    ~30 days rolling (renewed hourly by running agent)
```

The almanac is queried at: `https://agentverse.ai/v1/almanac/agents/{address}`

Health supervisor address: `agent1qwfjqkecc53x25fw5drn8mp2layafk3f64pu653hl2gy774ksuglg92w0sz`
Health worker address: `agent1q2rdf0ugjztjtc4hy272gxjgjncnfexrfz6l6at6dzqmr06f5jf97vt98ys`

All addresses are deterministic from seed phrases in `.env`. If seeds change, all
Agentverse registrations must be re-done via the Agent Inspector.

### 2.6 Shared runtime contracts and config

**Message models** (`agents/shared/models.py`)
- Sprint 1 scaffold models: `MockDomainTask`, `MockWorkerResult`, `MockSupervisorResult`
- Sprint 2+ production models (defined, not yet wired): `OnDemandDetectionRequest`,
  `ActionDraft`, `WorkerResult`, `SupervisorResult`, `ModificationRequest/Task/Draft/Result`,
  `QuestionRequest/Task/ApiResult/Answer`, `SchedulingQuery/Options`, `ExpirationEscalation`

**Constants** (`agents/shared/constants.py`)
- `AGENT_PORTS`: port assignments for all 10 agents
- `DOMAIN_KEYWORDS`: keyword-to-domain mapping for executor classification
- `URGENCY_SCORES`, `OVERDUE_SCORE_BOOST`, `DOMAIN_PRIORITY`: action ranking weights
- `REVIEW_BY_HOURS`: tier → expiry deadline in hours
- `EXPIRATION_CHECK_INTERVAL`: 900 s (15 min) — the only scheduled loop in the system
- `ORG_CONTEXT_MAP`: which org_profile fields are injected per domain in LLM prompts

**Config + resolver** (`agents/shared/config.py`)
- All seed phrases and agent addresses loaded from `.env` with deterministic fallbacks
- `SUPERVISOR_ADDRESS_BY_DOMAIN`: executor uses this to route by domain
- `LocalFirstResolver`: custom `Resolver` subclass — see section 2.2

**Request state** (`agents/shared/state_service.py`)
- In-memory `request_id → PendingRequest` map
- `PendingRequest` stores: `request_id`, `query`, `domain`, `user_sender_address`,
  `routed_address`, `created_at`
- Sweep runs every 15 s; requests older than 45 s are timed out and the user receives
  an error reply

### 2.7 Data layer

**Schema** (`data/schema.sql`)
Tables: `org_profile`, `patients`, `patient_updates`, `caregivers`,
`caregiver_schedule`, `patient_caregivers`, `emergency_contacts`, `medications`,
`caregiver_notes`, `appointments`, `grocery`, `grocery_staples`, `financial_bills`,
`financial_anomalies`, `action_history`, `action_chat`, `notifications`,
`expiration_notifications`

**Seed** (`data/seed.py`)
Deterministic reset — rebuilds DB from schema on every run:
- 1 org profile (Sunrise Care Org)
- 3 patients (pt_001 Margaret Chen, pt_002 Robert Harris, pt_003 Dorothy Kim)
- 10 caregivers (cg_001–cg_010)
- 14-day schedule expansion: 140 `caregiver_schedule` rows
- patient-caregiver assignments (cg_001 + cg_002 assigned to all 3 patients)
- 1 pre-seeded overdue action (pt_003 Metformin escalation, `is_overdue=1`)

**DB helpers** (`agents/shared/db.py`)
Full helper surface implemented: org, patient, patient_update, action (with
rank/scoring), chat, notification (with dedupe hooks), caregiver/scheduling.

### 2.8 API and dashboard scaffolding

**FastAPI** (`api/main.py`, port 8000)
- `GET /health` → `{"status":"ok"}`
- Router stubs mounted: `/actions`, `/patients`, `/caregivers`, `/scheduling`,
  `/notifications`, `/ingest`, `/org`
- All stub endpoints return placeholder responses. Sprint 2 wires them to `db.py`.

**React dashboard** (`dashboard/src/App.tsx`)
- React Router baseline: `/actions`, `/patients`, `/caregivers`, `/org`
- Placeholder content. Sprint 2 wires to real API responses.

---

## 3) Environment setup

### 3.1 Build `.venv`

```bash
python3 -m venv .venv
.venv/bin/python3 -m pip install -r requirements.txt
```

Apple Silicon (`arm64`) — if you hit `ImportError ... pydantic_core ... incompatible architecture`:

```bash
arch -arm64 python3 -m venv --clear .venv
arch -arm64 .venv/bin/python3 -m pip install -r requirements.txt
```

### 3.2 Required `.env` values

```
AGENTVERSE_API_KEY=<from agentverse.ai account settings>
EXECUTOR_SEED_PHRASE=<random string, no spaces>
HEALTH_SUPERVISOR_SEED_PHRASE=<random string>
# ... one per agent (see .env.example)

EXECUTOR_AGENT_ADDRESS=<derived from seed — read from startup log>
HEALTH_SUPERVISOR_ADDRESS=<derived from seed>
# ... one per agent

SQLITE_DB_PATH=data/life_graph.db
EXECUTOR_INTERNAL_URL=http://localhost:8001
MOCK_API_BASE=http://localhost:8000
ANTHROPIC_API_KEY=<for Sprint 2 LLM calls>
```

`AGENTVERSE_API_KEY` is not consumed by the uAgents library directly. It is used by
the Agentverse Agent Inspector UI session when you click Connect. The uAgents mailbox
client authenticates using the agent's own private key (derived from the seed phrase)
via a cryptographic attestation — no API key needed at runtime.

---

## 4) Validation commands

All commands assume `.venv` is active.

### 4.1 Compile check

```bash
python3 -m compileall agents api data -q
```

Expected: no output (silent = clean).

### 4.2 DB seed

```bash
python3 data/seed.py
python3 -c "
import sqlite3
con = sqlite3.connect('data/life_graph.db')
for table, expected in [('org_profile',1),('patients',3),('caregivers',10),
                         ('caregiver_schedule',140)]:
    n = con.execute(f'select count(*) from {table}').fetchone()[0]
    print(table, n, '✓' if n==expected else f'✗ expected {expected}')
print('overdue_actions',
      con.execute('select count(*) from action_history where is_overdue=1').fetchone()[0])
con.close()
"
```

### 4.3 API health

```bash
# Terminal A
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Terminal B
curl -s http://127.0.0.1:8000/health
# → {"status":"ok"}
```

### 4.4 Executor smoke test

```bash
# Terminal A
python3 -m agents.executor.agent

# Terminal B — REST routing
curl -s -X POST http://127.0.0.1:8001/message \
  -H "Content-Type: application/json" \
  -d '{"content":"health medication refill"}'
# → {"request_id":"...","routed_domain":"health","routed_address":"agent1q..."}

# Terminal B — mailbox queue state
curl -s http://127.0.0.1:8001/mailbox-debug | python3 -m json.tool
# → {"http_status":200,"item_count":0,...}  (0 = queue empty = healthy)
```

### 4.5 Full end-to-end pipeline (all agents)

```bash
# Terminal A
SQLITE_DB_PATH=data/life_graph.db \
EXECUTOR_INTERNAL_URL=http://localhost:8001 \
MOCK_API_BASE=http://localhost:8000 \
python3 -m agents.run_all

# Terminal B — triggers full executor → supervisor → worker → executor round-trip
curl -s -X POST http://127.0.0.1:8001/message \
  -H "Content-Type: application/json" \
  -d '{"content":"health refill test"}'
```

Expected terminal A output (all in < 1 s with LocalFirstResolver):
```
[executor]:         Routing request_id=... domain=health
[health-supervisor]: Received MockDomainTask ...
[health-supervisor]: Dispatching ... to health-worker
[health-supervisor]: Received MockWorkerResult ...
[health-supervisor]: Forwarding MockSupervisorResult to executor
[executor]:         Received MockSupervisorResult ... result=Health mock complete ...
[executor]:         Completed request_id=... for non-chat flow
```

### 4.6 Direct chat injection test

```bash
# Sends a signed ChatMessage envelope directly to the executor's Agentverse mailbox
# (bypasses ASI:One — useful for verifying the executor chat path without the UI)
python3 test_chat_direct.py
```

Expected: executor logs `Received ChatMessage sender=...` within 2 seconds, then
routes through the full pipeline and attempts to send the reply back.

### 4.7 Dependency sanity check

```bash
python3 -c "import uagents, fastapi, uvicorn, anthropic; print('deps-ok')"
```

---

## 5) ASI:One integration setup (per-machine, one-time)

This must be done **while all agents are running** and only after first-time startup
or after the agent seed phrases change.

1. Start all agents: `python3 -m agents.run_all`
2. Sign in to [agentverse.ai](https://agentverse.ai) and [asi1.ai](https://asi1.ai)
   with the **same account**.
3. Open the Agent Inspector for each of the 10 agents. The Inspector URL contains
   the agent's local port (e.g. `http://localhost:8001` for executor). Click
   **Connect** → **Select Mailbox** on each one.
4. Confirm mailbox is active: `curl -s http://127.0.0.1:8001/mailbox-debug` should
   show `"http_status": 200`.
5. To chat: from the **executor** Inspector, click **Go to Agent Profile** → **Chat
   with Agent**. This opens asi1.ai with the executor pre-targeted. Do NOT use the
   embedded chat inside the Inspector — it uses a direct connection path that bypasses
   the mailbox and silently fails for locally-running agents.
6. Verify receipt: after sending from asi1.ai, the executor terminal should log
   `Received ChatMessage sender=...` within a few seconds.

---

## 6) What Sprint 2 must implement

The scaffold mock pipeline must be replaced with real domain logic. Each supervisor
and worker stub needs:

**Supervisors** — replace `MockDomainTask` handler with:
- `OnDemandDetectionRequest` handler → fetch patient Life Graph → call LLM for
  detection → write actions to DB → return `SupervisorResult` to executor
- `ModificationRequest` handler → delegate to worker if live API needed → update
  draft in DB → write notification → return `ModificationResult`
- `QuestionRequest` handler → answer from Life Graph or delegate to worker → return
  `QuestionAnswer`

**Workers** — replace `MockDomainTask` handler with:
- Domain-specific detection logic using `call_claude()` from `agents/shared/llm.py`
- Live API calls where spec requires (OpenFDA, Google Maps, Instacart, Amazon)
- Return `WorkerResult` (list of `ActionDraft`) to supervisor

**Executor** — replace keyword classification with intent router:
- Intent: question → `QuestionRequest` → supervisor → `QuestionAnswer` → reply
- Intent: modification → `ModificationRequest` → health supervisor → `ModificationResult`
- Intent: scheduling → `SchedulingQuery` → scheduling agent → `SchedulingOptions`
- Detection: `OnDemandDetectionRequest` → all domain supervisors in parallel

**Key constraint:** The only scheduled loop is the 15-minute expiration check on the
executor. Supervisors have **no interval handlers** — all processing is event-driven.

---

## 7) Known non-obvious behaviours

**Silent message rejection in uAgents dispatcher**
If `allow_unverified=True` is missing from a `@proto.on_message` handler and the
sender uses a user-class address (e.g. ASI:One), uAgents dispatches an
`ErrorMessage("Message must be sent from verified agent address")` back to the sender
with no log output and never calls the handler. This is the canonical silent failure
mode for ASI:One chat not working.

**Mailbox 404 is logged only once**
If the Agentverse mailbox is not provisioned for an agent, the `MailboxClient`
logs `"Agent mailbox not found: create one using the agent inspector"` exactly once
and then silences the warning permanently (`_missing_mailbox_warning_logged = True`).
All subsequent poll failures are swallowed silently. Re-check with `/mailbox-debug`
if you suspect the mailbox is broken.

**Agentverse almanac registration expiry**
Registrations expire after ~30 days. A running agent renews automatically every hour.
If the agent was offline for 30+ days, re-do Connect → Select Mailbox in the
Inspector before testing ASI:One delivery.

**`LocalFirstResolver` and agent restart order**
`LocalFirstResolver` resolves to `http://localhost:{port}/submit`. If a target agent
(e.g. health-supervisor on port 8101) is not yet running when the executor tries to
route a message, the `ctx.send()` will fail. Always start all 10 agents before
sending queries. `run_all.py` handles this correctly.

**`test_chat_direct.py` sender is not in almanac**
The test script uses the health-supervisor's seed to sign the envelope (so the
executor can resolve and reply). An ephemeral `Identity.generate()` sender would cause
`Unable to resolve destination endpoint` on the reply — benign but noisy. The current
script uses the supervisor seed to avoid this.

---

## 8) Useful command reference

```bash
# Activate env
source .venv/bin/activate

# Seed DB
python3 data/seed.py

# Run API only
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Run executor only
python3 -m agents.executor.agent

# Run full stack
SQLITE_DB_PATH=data/life_graph.db \
EXECUTOR_INTERNAL_URL=http://localhost:8001 \
MOCK_API_BASE=http://localhost:8000 \
python3 -m agents.run_all

# Mailbox queue state
curl -s http://127.0.0.1:8001/mailbox-debug | python3 -m json.tool

# Direct chat injection test
python3 test_chat_direct.py

# Almanac lookup for executor
curl -s https://agentverse.ai/v1/almanac/agents/agent1qgs7zw0ce49c5k626tf8cag5wcjan7hhrpeguwlg836kkyjr69ypuwhms84 | python3 -m json.tool

# Compile check all agents
python3 -m compileall agents api data -q
```
