# MACOS

## Abstract
MACOS (Multi-Agent Care Operations System) is designed to help nonprofit caregiving organizations coordinate care for multiple patients and caregivers across health, appointments, groceries, and finances. The motivation in `MACOS_build_spec_v7_final.md` is to replace fragmented, manual follow-up workflows with a single event-driven operations layer: when patient information changes, domain agents detect risk, generate prioritized actions, and route those actions to caregivers through dashboard and chat workflows. The intended outcome is faster response to care issues, clearer accountability, and safer escalation handling with structured, auditable state.

## Project File Structure

### Target Structure (from `MACOS_build_spec_v7_final.md`)
```text
macos/
├── agents/
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── llm.py
│   │   └── constants.py
│   ├── executor/
│   │   └── agent.py
│   ├── health/
│   │   ├── supervisor.py
│   │   └── worker.py
│   ├── appointment/
│   │   ├── supervisor.py
│   │   └── worker.py
│   ├── grocery/
│   │   ├── supervisor.py
│   │   └── worker.py
│   ├── financial/
│   │   ├── supervisor.py
│   │   └── worker.py
│   ├── scheduling/
│   │   └── agent.py
│   └── run_all.py
├── api/
│   ├── main.py
│   ├── routers/
│   │   ├── patients.py
│   │   ├── actions.py
│   │   ├── caregivers.py
│   │   ├── scheduling.py
│   │   ├── notifications.py
│   │   ├── ingest.py
│   │   └── org.py
│   ├── mock_apis/
│   │   ├── cvs.py
│   │   ├── cal.py
│   │   ├── instacart.py
│   │   ├── amazon.py
│   │   └── caregivers.py
│   └── db_bridge.py
├── dashboard/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/client.ts
│       ├── components/
│       ├── pages/
│       ├── hooks/
│       └── types/index.ts
├── data/
│   ├── seed.py
│   ├── life_graph.db
│   └── schema.sql
├── .env.example
├── requirements.txt
├── package.json
└── README.md
```

### Current Sprint 1 Structure (implemented in this repo)
```text
agents/
  shared/{config.py,constants.py,db.py,llm.py,models.py,state_service.py}
  executor/agent.py
  {health,appointment,grocery,financial}/{supervisor.py,worker.py}
  scheduling/agent.py
  run_all.py
api/
  main.py
  routers/{actions.py,patients.py,caregivers.py,scheduling.py,notifications.py,ingest.py,org.py}
  mock_apis/__init__.py
dashboard/
  index.html
  vite.config.ts
  tailwind.config.ts
  src/{main.tsx,App.tsx}
data/
  schema.sql
  seed.py
  life_graph.db (generated)
```

## Full Implementation Target (Spec v7)
The full build defined in `MACOS_build_spec_v7_final.md` is an 11-sprint implementation:

1. Sprint 1: Foundation scaffold, schema, shared runtime contracts, deterministic seed, baseline agent topology, baseline dashboard routes.
2. Sprint 2: Mock external API routers, ingest pipelines (text/file), org endpoints, internal detect trigger, email integration.
3. Sprint 3: Health domain production logic (detection, risk scoring, modification pipeline, Q&A, live API checks).
4. Sprint 4: Appointment, grocery, and financial production logic with full detection + Q&A coverage.
5. Sprint 5: Full executor orchestration, expiration loop behavior, intent routing, patient-update workflows, and complete FastAPI router wiring.
6. Sprint 6: Scheduling agent query/selection flow with task state transitions.
7. Sprint 7: Dashboard View 1 (Action Feed) with action states, chat panel, modification UX, and urgency/overdue visualization.
8. Sprint 8: Dashboard View 2 (Patient Roster) with patient detail panels, update workflow UI, and update-history integration.
9. Sprint 9: Dashboard View 3 (Caregiver Management) with scheduling panel, assignment workflows, and 14-day schedule grid.
10. Sprint 10: Dashboard View 4 (Org Dashboard) with org summary, protocol panels, caregiver roster, and org metrics.
11. Sprint 11: End-to-end polish, full demo validation, README + demo artifacts, and submission packaging.

Core system behavior in the final target:
- 3-tier agent orchestration (Executor -> Supervisors -> Workers).
- Event-driven detection for patient changes (no supervisor interval loops).
- Single scheduled expiration loop on the Executor.
- SQLite-backed life graph and action/notification audit surface.
- ASI:One + dashboard pathways for caregiver interaction.

## What Is Currently Implemented (Sprint 1)
Implemented now:
- Repository scaffold for `agents/`, `api/`, `dashboard/`, and `data/`.
- Quickstarter-style multi-agent mock topology:
  - Executor orchestrator.
  - Domain supervisors/workers for health, appointment, grocery, financial.
  - Scheduling agent.
- Shared runtime modules:
  - `agents/shared/models.py` message contracts.
  - `agents/shared/constants.py` runtime constants.
  - `agents/shared/db.py` DB helper surface.
  - `agents/shared/llm.py` LLM wrapper utilities.
  - `agents/shared/config.py` startup config validation + local-first resolver.
- SQLite schema and deterministic seed data:
  - 1 `org_profile` row.
  - 3 patients.
  - 10 caregivers.
  - 140 schedule rows (14 days x 10 caregivers).
  - 1 seeded overdue action.
- API scaffold with mounted routers and health endpoint (`GET /health`).
- React dashboard scaffold with baseline 4 routes and placeholders.

Not implemented yet (Sprint 2+ scope):
- Production detection pipelines and live-domain business logic.
- Mock external API endpoints under `api/mock_apis/`.
- Fully wired CRUD/action APIs backed by live runtime behavior.
- Full four-view dashboard implementation and domain UX flows.

## Run Instructions (Sprint 1 Operations)

### 1. Clone and enter repo
```bash
git clone <your-repo-url>
cd Autocare
```

### 2. Set up Python environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you hit a `pydantic_core` architecture mismatch on macOS (Apple Silicon), recreate using arm64:
```bash
arch -arm64 python3 -m venv --clear .venv
arch -arm64 .venv/bin/python -m pip install -r requirements.txt
source .venv/bin/activate
```

### 3. Configure environment
```bash
cp .env.example .env
```

For local Sprint 1 scaffold checks, set at minimum:
- `SQLITE_DB_PATH=data/life_graph.db`
- `EXECUTOR_INTERNAL_URL=http://localhost:8001`
- `MOCK_API_BASE=http://localhost:8000`

Optional for mailbox/chat integration on Agentverse/ASI:One:
- Agent seed phrases and registered addresses.
- `AGENTVERSE_API_KEY`.

### 4. Seed and verify DB baseline
```bash
python data/seed.py
python -c "import sqlite3; con=sqlite3.connect('data/life_graph.db');
print('org_profile', con.execute('select count(*) from org_profile').fetchone()[0]);
print('patients', con.execute('select count(*) from patients').fetchone()[0]);
print('caregivers', con.execute('select count(*) from caregivers').fetchone()[0]);
print('caregiver_schedule', con.execute('select count(*) from caregiver_schedule').fetchone()[0]);
print('overdue_actions', con.execute('select count(*) from action_history where is_overdue=1').fetchone()[0]);
con.close()"
```

Expected counts:
- `org_profile = 1`
- `patients = 3`
- `caregivers = 10`
- `caregiver_schedule = 140`
- `overdue_actions = 1`

### 5. Foundation compile check
```bash
python -m compileall agents api data -q
```

### 6. Run API scaffold
```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

In another terminal:
```bash
curl -s http://127.0.0.1:8000/health
```

Expected response:
```json
{"status":"ok"}
```

### 7. Run full Sprint 1 agent stack
```bash
SQLITE_DB_PATH=data/life_graph.db \
EXECUTOR_INTERNAL_URL=http://localhost:8001 \
MOCK_API_BASE=http://localhost:8000 \
python -m agents.run_all
```

### 8. Run executor routing smoke call
In another terminal while the stack is running:
```bash
curl -s -X POST http://127.0.0.1:8001/message \
  -H "Content-Type: application/json" \
  -d '{"content":"health refill test"}'
```

Expected behavior:
- Executor classifies and routes to health supervisor.
- Health supervisor forwards to health worker.
- Worker responds; supervisor returns to executor.
- Executor completes request lifecycle.

### 9. Optional: direct chat pipeline test
```bash
python test_chat_direct.py
```

This sends a signed chat envelope to the executor path for local chat-flow verification.

## Primary References
- `MACOS_build_spec_v7_final.md`
- `CLAUDE.md`
- `openspec/changes/archive/2026-04-25-implement-sprint-1-foundation/`
