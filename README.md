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

### Current Structure (fully implemented)
```text
agents/
  shared/{config.py,constants.py,db.py,llm.py,models.py,state_service.py,notifications.py}
  executor/agent.py          # Intent routing, fan-out, expiration loop
  {health,appointment,grocery,financial}/{supervisor.py,worker.py,openfda.py}
  scheduling/agent.py        # Scheduling query/selection state machine
  run_all.py
api/
  main.py
  routers/{actions.py,patients.py,caregivers.py,scheduling.py,notifications.py,ingest.py,org.py}
  mock_apis/                 # CVS, calendar, Instacart, Amazon, caregiver mock endpoints
dashboard/
  index.html
  vite.config.ts
  playwright.config.ts
  src/
    main.tsx                 # Redux Provider, lazy-loaded routes
    components/
      AppShell.tsx           # TopBar + NavTabs
      ActionCard.tsx         # Polymorphic card (health-modify, Q&A, scheduling)
      ActionChatPanel.tsx    # Slide-over chat drawer with 3s polling
      DraftModal.tsx         # Inline draft edit + PATCH submission
    views/
      ActionFeed.tsx         # 10s polling, urgency-sorted action cards
      PatientRoster.tsx      # Split layout, add/update workflows, staged confirmation
      CaregiverManagement.tsx# Scheduling strip, 14-day grid, confirm/decline
      OrgDashboard.tsx       # Org summary, protocol cards, metrics, edit form
    api/client.ts            # RTK Query API slice (all endpoints)
    types/index.ts           # Shared TypeScript interfaces
  e2e/                       # Playwright E2E tests for all four views
data/
  schema.sql
  seed.py
  life_graph.db (generated)
tests/
  integration/               # FastAPI integration tests (patient update, ingest, detect)
  test_health_detection.py
  test_appointment_detection.py
  test_grocery_detection.py
  test_financial_detection.py
  test_scheduling_e2e.py
  test_expiration_loop.py
docs/
  architecture.md
  demo-checklist.md
```

## What Is Implemented

### Backend
- Full multi-agent stack: Executor → Domain Supervisors → Workers (health, appointment, grocery, financial, scheduling).
- Event-driven patient detection fan-out on `patient_create` and `patient_update` triggers.
- Scheduling agent: query → options → numeric selection → `pending_approval → unconfirmed → confirmed/declined` lifecycle.
- Expiration loop: marks overdue actions, emits deduped notifications per channel (dashboard, ASI:One).
- Patient ingest: text and file (PDF/image) → LLM extraction → write patient → trigger detect.
- Patient update: staged confirmation state machine → confirm → trigger detect with domain hint.
- Full FastAPI REST surface: patients, actions, caregivers, scheduling, notifications, ingest, org.

### API Contract
All endpoints return `{"success": true, "data": ...}` or `{"success": false, "error": "..."}`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/actions?sort=rank` | List pending actions sorted by urgency score |
| PATCH | `/actions/{id}` | Submit modification instruction or mark reviewed |
| POST | `/actions/{id}/chat` | Send chat message to assistant |
| GET | `/actions/{id}/chat-history` | Fetch chat history |
| GET | `/patients` | Enriched patient list (pending counts, urgency) |
| GET | `/patients/{id}` | Full patient detail with life graph |
| POST | `/patients/{id}/update` | Propose update (staged) |
| POST | `/patients/{id}/update/{uid}/confirm` | Confirm staged update |
| GET | `/patients/{id}/update-history` | Update history log |
| POST | `/ingest/text` | Ingest free-form patient text |
| POST | `/ingest/file` | Ingest PDF or image file |
| GET | `/caregivers` | List caregivers with availability |
| GET | `/caregivers/{id}/schedule` | 14-day schedule grid |
| GET | `/caregivers/{id}/assignments` | Assignment list |
| POST | `/scheduling/{id}/assign` | Assign caregiver → unconfirmed |
| POST | `/scheduling/{id}/confirm` | Confirm → completed=1 |
| POST | `/scheduling/{id}/decline` | Decline → reset to pending_approval |
| GET | `/org` | Org profile |
| PUT | `/org` | Update org profile |

### Dashboard (four views)
- **Action Feed**: RTK Query polling (10s), urgency-sorted cards, OVERDUE banners, tier badges, `ActionChatPanel` slide-over (3s chat poll), `DraftModal` with idempotency key, modification-in-progress lock, scheduling deep-link.
- **Patient Roster**: Two-column split layout, sidebar with urgency pills, life graph sections (health/appointments/grocery/financial/emergency contacts), pending actions summary, action history accordion, Add Patient modal (text + file tabs), staged update confirmation state machine, Update History tab.
- **Caregiver Management**: Scheduling strip (pending_approval + unconfirmed actions), assignment dropdowns, Confirm/Decline buttons, caregiver detail panel, 14-day schedule grid, assignment list, deep-link preselect from Action Feed.
- **Org Dashboard**: Org summary panel, four metric cards (total pending, total overdue, 30-day completion rate, avg urgency score), protocol cards, caregiver roster table, Edit Org Profile form.

### Test Coverage
- Backend integration tests: patient update pipeline, file ingest, executor fan-out logic.
- Domain detection unit tests: health, appointment, grocery, financial — parse pipeline with deterministic seed data.
- Scheduling E2E tests: assign → unconfirmed → confirm/decline status transitions.
- Expiration loop tests: dedup notification per channel, overdue marking.
- Dashboard E2E tests (Playwright): all four views, critical UX flows.

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
