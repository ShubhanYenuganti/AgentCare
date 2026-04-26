# AgentCare (MACOS)

## Abstract
AgentCare is a multi-layer autonomous care-operations system built to support caregiver teams running real-world patient workloads across health, appointments, groceries, and financial follow-ups. It combines ingestion pipelines, domain-specific agents, deterministic task state management, and operator-facing UI workflows into one coordinated runtime.

The core operating model is event-driven:
- caregivers ingest or update patient data,
- the executor fans that context across domain supervisors/workers,
- autonomous tasks are generated and queued with urgency classification,
- manual tasks are created with explicit, verbose caregiver instructions and scheduling metadata,
- overdue detection escalates risk and pushes alerts to dashboard + ASI:One channels.

It also provides built-in explainability interfaces at two scopes:
- task-scoped reasoning (why this action exists, what it will do, what changed),
- organization/patient-profile scope (cross-patient operational questions, pending risk, and workload state).

Modification support is currently constrained by policy: **task modification is enabled for the health domain only**.

---

## ASI:One Overdue Signaling

ASI:One is actively used as an overdue escalation channel in this implementation.

When the expiration pipeline detects an overdue action, the system:
1. marks the action overdue and escalates urgency,
2. writes a dashboard notification,
3. sends a `ChatMessage` to the configured ASI:One care coordinator address (`ASI_ONE_AGENT_ADDRESS`),
4. records dedup entries so each overdue action is signaled once per channel.

For immediate validation (without waiting for the 15-minute interval), use:
- `POST /internal/expiration-check` with `{"force_overdue": true}`.

---

## What The System Does

### 1. Multi-layer autonomous orchestration
- **Executor agent** performs intent classification and routing.
- **Domain supervisors/workers** (health, appointment, grocery, financial) generate and refine actions.
- **Scheduling agent** manages assignment state transitions and caregiver availability workflows.

### 2. Ingestion flows that queue autonomous tasks
- Free-text and file-based patient ingestion (`/ingest/text`, `/ingest/file`).
- Staged patient updates with explicit confirm step (`/patients/{id}/update/.../confirm`).
- Confirmed updates trigger detection fan-out and action creation.

### 3. Autonomous + manual task support
- Actions are persisted in `action_history` with urgency, domain, lifecycle state, and execution payload context.
- Manual/scheduling actions include caregiver-facing instructions and schedule windows used by caregiver roster tooling.
- Approvals execute route-backed automations where payload requirements are satisfied.

### 4. Urgency and overdue lifecycle
- Urgency tiers (`tier_0`..`tier_3`) plus domain weighting support global ranking.
- Expiration loop marks actions overdue and emits deduped notifications.
- Overdue alerts are sent to:
  - dashboard notification feed,
  - ASI:One target address (when `ASI_ONE_AGENT_ADDRESS` is configured).

### 5. Explainability and assistant interfaces
- **Task-scoped chat:** `/actions/{action_id}/chat` and `/actions/{action_id}/chat-history`.
- **General org/patient chat:** `/chat` session pipeline backed by executor `/general-chat`.
- Supports question answering, draft-action generation, and draft revision/approval flows.

### 6. Modification scope
- Health-domain action modification is supported in production flow.
- Non-health domain modification is intentionally out-of-scope in current policy config.

---

## Staging Actions From Chat

Caregivers can request new actions directly in the general chat interface. Those requests are
staged first, then explicitly approved into `action_history`.

Staging flow:
1. Send message to `POST /chat` with no `session_id` to open a new chat session.
2. Continue the conversation in the same `session_id` until the assistant returns `stage: "draft_ready"` and a `draft_action_id`.
3. Optional: revise draft with `POST /chat/action/{draft_action_id}/modify`.
4. Approve draft with `POST /chat/action/{draft_action_id}/approve` to commit it as a real action.
5. Or discard with `POST /chat/action/{draft_action_id}/discard`.

Example:
```bash
# 1) Create session + request a new action
RESP=$(curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Create a health follow-up action for Dorothy Kim to check medication adherence this week."}')
echo "$RESP" | python3 -m json.tool

SESSION_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['session_id'])")

# 2) Continue chat (if clarification is requested)
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"${SESSION_ID}\",\"message\":\"Yes, that is correct. Make it urgent tier_1.\"}" | python3 -m json.tool

# 3) Get draft_action_id from history
HIST=$(curl -s "http://localhost:8000/chat/history?session_id=${SESSION_ID}")
echo "$HIST" | python3 -m json.tool
DRAFT_ACTION_ID=$(echo "$HIST" | python3 -c 'import sys,json; msgs=json.load(sys.stdin)["data"]; print(next((m.get("draft_action_id") for m in reversed(msgs) if m.get("draft_action_id")), ""))')

# 4) Optional modify
curl -s -X POST "http://localhost:8000/chat/action/${DRAFT_ACTION_ID}/modify" \
  -H "Content-Type: application/json" \
  -d '{"feedback":"Add explicit caregiver check-in instructions and include blood glucose note."}' | python3 -m json.tool

# 5) Approve staged draft into action_history
curl -s -X POST "http://localhost:8000/chat/action/${DRAFT_ACTION_ID}/approve" | python3 -m json.tool
```

After approval, the new action appears in `/actions` and in the dashboard feeds.

---

## End-to-End Runtime Flow

1. Data enters through ingest/update endpoints.
2. Executor receives trigger and selects detection fan-out path.
3. Domain workers emit action drafts with urgency, instructions, and optional automation payload templates.
4. Actions appear in Action Feed and Patient/Caregiver views.
5. Caregiver can:
- approve,
- dismiss,
- assign/confirm scheduling,
- ask scoped questions,
- request modification (health domain).
6. Approval executes automation calls (mock APIs and optional integrations), stores execution result, and updates lifecycle state.
7. Expiration loop escalates overdue work and emits deduped notifications (dashboard + ASI:One).

---

## Key Interfaces

### Core REST APIs (FastAPI)
- `GET /actions?sort=rank|created_at`
- `GET /actions/{id}`
- `PATCH /actions/{id}`
- `POST /actions/{id}/approve`
- `POST /actions/{id}/complete`
- `POST /actions/{id}/dismiss`
- `POST /actions/{id}/chat`
- `GET /actions/{id}/chat-history`

- `GET /patients`
- `GET /patients/{id}`
- `POST /patients`
- `PUT /patients/{id}`
- `POST /patients/{id}/update`
- `POST /patients/{id}/update/file`
- `POST /patients/{id}/update/{update_id}/confirm`
- `GET /patients/{id}/update-history`

- `POST /ingest/text`
- `POST /ingest/file`

- `GET /caregivers`
- `GET /caregivers/{id}/schedule`
- `GET /caregivers/{id}/assignments`

- `POST /scheduling/{action_id}/assign`
- `POST /scheduling/{action_id}/confirm`
- `POST /scheduling/{action_id}/decline`

- `GET /org`
- `PUT /org`
- `PATCH /org`

- `GET /notifications`
- `POST /notifications/{id}/read`

- `POST /chat` (general assistant)
- `GET /chat/history`
- `POST /chat/action/{draft_action_id}/approve`
- `POST /chat/action/{draft_action_id}/modify`
- `POST /chat/action/{draft_action_id}/discard`

### Executor internal endpoints
- `POST /internal/detect` — trigger detection fan-out.
- `POST /internal/expiration-check` — one-shot overdue pass (optional forced-overdue action) to invoke alert path immediately.

### Mock automation routes
- `POST /mock/cvs/refill`
- `POST /mock/cal/book`
- `POST /mock/instacart/cart`
- `POST /mock/amazon/order`
- `POST /mock/amazon/reorder`
- `POST /mock/caregivers/available`

---

## Dashboard Surfaces

- **Action Feed**
- urgency-ranked actions, approval/dismiss controls, task chat, execution visibility.

- **Patient Roster**
- patient-centric profile + life-graph context + pending/history actions.

- **Caregiver Management**
- assignment controls, scheduling states, caregiver availability and 14-day grid.

- **Org Dashboard**
- org profile summary, operational metrics, protocol context, caregiver roster view.

---

## Overdue + ASI:One Auto-Flagger

When the expiration pass runs:
1. pending actions with `review_by < now` are marked overdue,
2. urgency escalates (`tier_0` path),
3. dashboard notification is written,
4. ASI:One alert is sent via `ctx.send(ASI_ONE_AGENT_ADDRESS, ChatMessage)` when configured,
5. dedup entries are persisted in `expiration_notifications` per channel.

This guarantees one alert per channel per action unless state is explicitly reset.

---

## Local Setup

### Prerequisites
- Python 3.11+
- Node 18+
- `pip`, `npm`

### 1) Install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd dashboard
npm install
cd ..
```

### 2) Configure environment
```bash
cp .env.example .env
```

Required runtime vars for full stack:
- `SQLITE_DB_PATH=data/life_graph.db`
- `EXECUTOR_INTERNAL_URL=http://localhost:8001`
- `MOCK_API_BASE=http://localhost:8000`

Optional for ASI:One overdue alerts:
- `ASI_ONE_AGENT_ADDRESS=agent1q...`

### 3) Seed deterministic data
```bash
source .venv/bin/activate
python3 data/seed.py
```

### 4) Start backend + agents
```bash
source .venv/bin/activate
SQLITE_DB_PATH=data/life_graph.db \
EXECUTOR_INTERNAL_URL=http://localhost:8001 \
MOCK_API_BASE=http://localhost:8000 \
python3 -m agents.run_all
```

### 5) Start frontend
```bash
cd dashboard
npm run dev
```

Open:
- API: `http://localhost:8000`
- Executor: `http://localhost:8001`
- Dashboard: `http://localhost:5173`

---

## Quick Validation

### Health check
```bash
curl -s http://127.0.0.1:8000/health
```

### Seed sanity check
```bash
python3 - <<'PY'
import sqlite3
con = sqlite3.connect('data/life_graph.db')
for q, name in [
    ('select count(*) from org_profile', 'org_profile'),
    ('select count(*) from patients', 'patients'),
    ('select count(*) from caregivers', 'caregivers'),
    ('select count(*) from action_history', 'actions')
]:
    print(name, con.execute(q).fetchone()[0])
con.close()
PY
```

### Force immediate overdue pass (no 15-minute wait)
```bash
curl -s -X POST http://localhost:8001/internal/expiration-check \
  -H "Content-Type: application/json" \
  -d '{"force_overdue": true}'
```

---

## Repository Layout (Current)

```text
agents/
  executor/agent.py
  health/{supervisor.py,worker.py}
  appointment/{supervisor.py,worker.py}
  grocery/{supervisor.py,worker.py}
  financial/{supervisor.py,worker.py}
  scheduling/agent.py
  shared/{config.py,constants.py,db.py,llm.py,models.py,notifications.py,state_service.py}
  run_all.py

api/
  main.py
  routers/{actions.py,caregivers.py,chat.py,ingest.py,notifications.py,org.py,patients.py,scheduling.py}
  mock_apis/router.py

dashboard/
  src/{api,components,types,utils,views}
  e2e/

data/
  schema.sql
  seed.py
  life_graph.db (generated)

demo/
  README.md
  payloads/
  uploads/

tests/
  integration/
  test_*.py
```

---

## Notes
- This repo is intentionally agent-first and event-driven.
- Detection and action generation quality depends on runtime model configuration and available context.
- Automation execution requires valid action payload templates; route preflight errors are surfaced in action execution plans.
- Current modification policy is intentionally limited to health-domain workflows.
