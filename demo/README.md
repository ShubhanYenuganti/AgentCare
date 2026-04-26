# Autocare Demo Setup

Three tracks depending on how much you want to see. All start with a fresh SQLite database.

---

## Track A — Storyboard Quick Start (~15 minutes)

This is the canonical demo track. It seeds deterministic data, applies a fixed storyline, and
demonstrates the ASI:One auto-flagger without waiting 15 minutes.

Track A outcomes:
- Multiple patients and caregivers in play
- At least 3 health actions
- At least one action with a `schedule` payload
- Automation-ready actions for:
  - `POST /mock/cal/book`
  - `POST /mock/cvs/refill`
  - `POST /mock/instacart/cart`
  - `POST /mock/amazon/order`
- One forced overdue action that immediately invokes the ASI:One send path

### Step 0 — Seed + start full stack (with ASI:One target)

Terminal A:
```bash
python3 data/seed.py

ASI_ONE_AGENT_ADDRESS=agent1q_your_care_coordinator_address \
SQLITE_DB_PATH=data/life_graph.db \
EXECUTOR_INTERNAL_URL=http://localhost:8001 \
MOCK_API_BASE=http://localhost:8000 \
python3 -m agents.run_all
```

Terminal B:
```bash
cd dashboard
npm run dev
```

Open: http://localhost:5173

### Step 1 — Verify baseline and normalize deadlines to future
```bash
curl -s http://localhost:8000/patients | python3 -m json.tool
curl -s http://localhost:8000/caregivers | python3 -m json.tool

python3 - <<'PY'
import sqlite3
con = sqlite3.connect("data/life_graph.db")
con.execute("""
UPDATE action_history
SET is_overdue = 0,
    review_by = strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '+2 day')
WHERE completed = 0
""")
con.commit()
print("Normalized pending actions to non-overdue baseline.")
PY

curl -s "http://localhost:8000/actions?sort=rank" | python3 -m json.tool
```

Expected baseline:
- 3 patients and 10 caregivers are present
- pending actions exist
- all pending actions are non-overdue before the forced-overdue demo step

### Step 2 — Apply storyboard updates (upload + confirm)

Use this helper to upload each update file and immediately confirm it:

```bash
apply_update () {
  local patient_id="$1"
  local file="$2"
  echo ""
  echo "==> ${patient_id} :: ${file}"
  RESP=$(curl -s -X POST "http://localhost:8000/patients/${patient_id}/update/file" -F "file=@${file}")
  echo "$RESP" | python3 -m json.tool
  UPDATE_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['update_id'])")
  curl -s -X POST "http://localhost:8000/patients/${patient_id}/update/${UPDATE_ID}/confirm" | python3 -m json.tool
}

# Health (3+ expected)
apply_update pt_003 demo/uploads/updates/dorothy_missed_metformin.txt
apply_update pt_001 demo/uploads/updates/margaret_lisinopril_refill.txt
apply_update pt_002 demo/uploads/updates/robert_tiotropium_refill.txt

# Appointment booking (calendar automation path)
apply_update pt_001 demo/uploads/updates/margaret_cardiology_booking_upcoming.txt

# Scheduling/transport (should produce schedule payload action)
apply_update pt_002 demo/uploads/updates/robert_pt_transport_with_window.txt

# Grocery automations
apply_update pt_003 demo/uploads/updates/dorothy_instacart_cart.txt
apply_update pt_003 demo/uploads/updates/dorothy_amazon_household_order.txt
```

Expected storyline outcomes after Step 2:
- Health actions increase to at least 3 active items
- Appointment actions include at least one booking-oriented task
- At least one action contains a non-null `schedule` object
- Grocery actions include Instacart-style and Amazon-style automation intents

### Step 3 — Hard validation gate (must pass before approvals)
```bash
curl -s "http://localhost:8000/actions?sort=rank" | python3 - <<'PY'
import json, sys

payload = json.load(sys.stdin)
actions = payload.get("data", [])
pending = [a for a in actions if not a.get("completed")]

health_count = sum(1 for a in pending if a.get("domain") == "health")
overdue_count = sum(1 for a in pending if int(a.get("is_overdue") or 0) == 1)
schedule_count = sum(1 for a in pending if a.get("schedule"))

required_routes = {
    "POST /mock/cal/book",
    "POST /mock/cvs/refill",
    "POST /mock/instacart/cart",
    "POST /mock/amazon/order",
}

present_routes = set()
preflight_errors = []
for a in pending:
    ep = a.get("execution_plan") or {}
    route = ep.get("inferred_route")
    if route:
        present_routes.add(route)
    for step in ep.get("steps") or []:
        route = step.get("route")
        if route:
            present_routes.add(route)
        errs = step.get("preflight_errors") or []
        if errs:
            preflight_errors.append((a.get("action_id"), route, errs))

missing = sorted(required_routes - present_routes)

print("health_count =", health_count)
print("overdue_count =", overdue_count)
print("schedule_count =", schedule_count)
print("present_routes =", sorted(present_routes))
print("missing_required_routes =", missing)
print("preflight_error_count =", len(preflight_errors))
for item in preflight_errors:
    print("preflight_error =", item)

ok = True
if health_count < 3:
    print("FAIL: expected at least 3 health actions")
    ok = False
if overdue_count != 0:
    print("FAIL: expected zero overdue actions")
    ok = False
if schedule_count < 1:
    print("FAIL: expected at least one action with schedule payload")
    ok = False
if missing:
    print("FAIL: missing one or more required automation routes")
    ok = False
if preflight_errors:
    print("FAIL: one or more actions have execution preflight errors")
    ok = False

if not ok:
    sys.exit(1)
print("PASS: Track A validation gate passed")
PY
```

### Step 4 — Force one action overdue and invoke ASI:One path immediately
```bash
TARGET_ACTION_ID=$(curl -s "http://localhost:8000/actions?sort=rank" | python3 -c '
import json,sys
rows = json.load(sys.stdin).get("data", [])
for a in rows:
    if not a.get("completed") and not a.get("is_overdue"):
        print(a["action_id"])
        raise SystemExit(0)
print("")
')

echo "Forcing overdue action_id=${TARGET_ACTION_ID}"
curl -s -X POST http://localhost:8001/internal/expiration-check \
  -H "Content-Type: application/json" \
  -d "{\"force_overdue\": true, \"action_id\": \"${TARGET_ACTION_ID}\"}" | python3 -m json.tool

curl -s "http://localhost:8000/actions?sort=rank&is_overdue=true" | python3 -m json.tool
curl -s "http://localhost:8000/notifications" | python3 -m json.tool

python3 - <<'PY'
import json, sqlite3
con = sqlite3.connect("data/life_graph.db")
con.row_factory = sqlite3.Row
rows = [
    dict(r)
    for r in con.execute(
        "SELECT action_id, channel, notified_at FROM expiration_notifications ORDER BY id DESC LIMIT 10"
    )
]
print(json.dumps(rows, indent=2))
PY
```

Expected outcomes:
- `POST /internal/expiration-check` returns `status: "triggered"` with a non-null `forced_action_id`
- overdue actions list includes the forced action
- at least one unread dashboard notification is present
- `expiration_notifications` contains entries for `dashboard` and `asi_one` for that action
- when `ASI_ONE_AGENT_ADDRESS` is valid/reachable, `alerts_sent_asi_one` should be `1`

### Step 5 — Approve one action per required automation route
```bash
ROUTES=(
  "POST /mock/cal/book"
  "POST /mock/cvs/refill"
  "POST /mock/instacart/cart"
  "POST /mock/amazon/order"
)

for ROUTE in "${ROUTES[@]}"; do
  ACTION_ID=$(curl -s "http://localhost:8000/actions?sort=rank" | python3 -c '
import json,sys
route = sys.argv[1]
rows = json.load(sys.stdin).get("data", [])
for a in rows:
    ep = a.get("execution_plan") or {}
    if ep.get("inferred_route") == route and not a.get("completed"):
        print(a["action_id"])
        raise SystemExit(0)
print("")
' "$ROUTE")

  if [ -z "$ACTION_ID" ]; then
    echo "No pending action found for route: $ROUTE"
    continue
  fi

  echo ""
  echo "==> Approving $ACTION_ID ($ROUTE)"
  curl -s -X POST "http://localhost:8000/actions/${ACTION_ID}/approve" | python3 -m json.tool
done
```

Expected approval outcomes:
- each approved route returns `success: true` with execution details
- action `outcome` transitions to `approved` and `completed=1`
- API confirmations appear in response payloads (`confirmation_id`, `cart_id`, `order_id`, etc.)

### Step 6 — Final verification snapshot
```bash
curl -s "http://localhost:8000/actions?sort=rank" | python3 -m json.tool
```

Expected final state:
- required automation routes have at least one successfully approved action each
- one forced-overdue action was flagged and notification dedup records were written
- health actions are still the dominant category (>=3 total during run)
- dashboard reflects completed autonomous execution counters

---

## Track B — API walkthrough (~10 minutes, shows pipeline live)

Demonstrates every ingestion and update endpoint. Watch actions appear in the dashboard in real time.

**Prerequisites:** both servers running (`bash demo/quick_start.sh` first, or start them manually).

### 1. Set org profile
```bash
curl -s -X PUT http://localhost:8000/org \
  -H "Content-Type: application/json" \
  -d @demo/payloads/org_setup.json | python3 -m json.tool
```

### 2. Create caregivers (5 new caregivers via POST /caregivers)
```bash
for f in demo/payloads/caregivers/*.json; do
  echo "Creating caregiver from $f..."
  curl -s -X POST http://localhost:8000/caregivers \
    -H "Content-Type: application/json" \
    -d @"$f" | python3 -m json.tool
done
```

### 3. Ingest patients (POST /ingest/text)
```bash
curl -s -X POST http://localhost:8000/ingest/text \
  -H "Content-Type: application/json" \
  -d @demo/payloads/patients/margaret_chen.json | python3 -m json.tool

curl -s -X POST http://localhost:8000/ingest/text \
  -H "Content-Type: application/json" \
  -d @demo/payloads/patients/robert_harris.json | python3 -m json.tool

curl -s -X POST http://localhost:8000/ingest/text \
  -H "Content-Type: application/json" \
  -d @demo/payloads/patients/dorothy_kim.json | python3 -m json.tool
```

### 4. Upload update documents to trigger domain actions

Each file targets a specific patient and domain. The upload returns a proposed update — you must confirm it to trigger the domain agent and generate an action.

**Health: Dorothy's missed Metformin (tier_0)**
```bash
# Upload
RESP=$(curl -s -X POST http://localhost:8000/patients/pt_003/update/file \
  -F "file=@demo/uploads/updates/dorothy_missed_metformin.txt")
echo "$RESP" | python3 -m json.tool

# Extract update_id and confirm
UPDATE_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['update_id'])")
curl -s -X POST "http://localhost:8000/patients/pt_003/update/${UPDATE_ID}/confirm" | python3 -m json.tool
```

**Appointment: Margaret's overdue cardiology (tier_1)**
```bash
RESP=$(curl -s -X POST http://localhost:8000/patients/pt_001/update/file \
  -F "file=@demo/uploads/updates/margaret_cardiology_overdue.txt")
UPDATE_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['update_id'])")
curl -s -X POST "http://localhost:8000/patients/pt_001/update/${UPDATE_ID}/confirm" | python3 -m json.tool
```

**Financial: Robert's PG&E anomaly (tier_1)**
```bash
RESP=$(curl -s -X POST http://localhost:8000/patients/pt_002/update/file \
  -F "file=@demo/uploads/updates/robert_pge_anomaly.txt")
UPDATE_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['update_id'])")
curl -s -X POST "http://localhost:8000/patients/pt_002/update/${UPDATE_ID}/confirm" | python3 -m json.tool
```

**Scheduling: Robert's PT transport (tier_1)**
```bash
RESP=$(curl -s -X POST http://localhost:8000/patients/pt_002/update/file \
  -F "file=@demo/uploads/updates/robert_pt_transport.txt")
UPDATE_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['update_id'])")
curl -s -X POST "http://localhost:8000/patients/pt_002/update/${UPDATE_ID}/confirm" | python3 -m json.tool
```

**Grocery: Dorothy's lapsed delivery (tier_2)**
```bash
RESP=$(curl -s -X POST http://localhost:8000/patients/pt_003/update/file \
  -F "file=@demo/uploads/updates/dorothy_grocery_reorder.txt")
UPDATE_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['update_id'])")
curl -s -X POST "http://localhost:8000/patients/pt_003/update/${UPDATE_ID}/confirm" | python3 -m json.tool
```

### 5. View generated actions
```bash
curl -s http://localhost:8000/actions?sort=rank | python3 -m json.tool
```

Or open the dashboard: http://localhost:5173

---

## Track C — In-app Onboarding Wizard (~15 minutes, best for stakeholder demos)

When the database is empty (no org profile saved), the dashboard automatically redirects to a guided onboarding wizard at `/onboarding`. No manual navigation required.

### Step 1 — Organization (wizard)
Open http://localhost:5173. You will land on the onboarding wizard automatically.

Fill in:
- **Organization Name** (required) — e.g. "Sunrise Care Partners"
- **Care Philosophy** — describes the tone agents use when drafting actions
- **Escalation Lead** — name of the supervising clinician

Click **Save & Continue**.

### Step 2 — Add Caregivers (wizard)
Click **+ Add Caregiver**. An inline form appears with:
- Name, email, phone, role
- A per-day schedule table — check each working day and set start/end hours

Submit — the caregiver appears in the green confirmation list. Add as many as you like, then click **Continue**.

Sample caregiver payloads are in `demo/payloads/caregivers/` if you want specific data.

### Step 3 — Add a Patient (wizard)
Upload a patient intake document. Sample files are in `demo/uploads/intake/`:
- `margaret_chen_intake.txt` — creates Margaret Chen
- `robert_harris_intake.txt` — creates Robert Harris
- `dorothy_kim_intake.txt` — creates Dorothy Kim

Click **Upload & Extract** — the AI parses the document and creates a structured patient profile. Add as many patients as you like, then click **Continue**.

### Step 4 — Ready (wizard)
The wizard shows a summary and a **Go to Dashboard** button which navigates to the Action Feed.

### Step 5 — Generate actions
- Navigate to **Patients** → select a patient → open the **Update** tab
- Click **Upload File** and select any file from `demo/uploads/updates/`:
  - `dorothy_missed_metformin.txt` → health action (tier_0, Metformin non-adherence)
  - `margaret_cardiology_overdue.txt` → appointment action (8 months overdue)
  - `robert_pge_anomaly.txt` → financial action ($340 utility anomaly)
  - `robert_pt_transport.txt` → scheduling action (PT transport needed Apr 28)
  - `dorothy_grocery_reorder.txt` → grocery action (12-day delivery lapse)
- Review the proposed changes and click **Confirm**
- Switch to **Action Feed** to see the generated action

### Step 6 — Work an action
- Click any action card to expand it
- Review draft content, urgency level, and domain
- Click **Approve** to execute, **Dismiss** to close, or type in the chat to ask the AI to revise
- For scheduling actions: click **View Scheduling** → assign a caregiver from the Caregivers panel

---

## File Map

```
demo/
  README.md                            ← this file
  quick_start.sh                       ← automated setup

  payloads/
    org_setup.json                     ← PUT /org
    patients/
      margaret_chen.json               ← POST /ingest/text
      robert_harris.json
      dorothy_kim.json
    caregivers/
      sarah_okafor.json                ← POST /caregivers
      james_reyes.json
      linda_park.json
      marcus_webb.json
      tom_callahan.json

  uploads/
    intake/
      margaret_chen_intake.txt         ← POST /ingest/file (creates patient)
      robert_harris_intake.txt
      dorothy_kim_intake.txt
    updates/
      margaret_lisinopril_refill.txt   ← Track A health refill storyline (CVS path)
      robert_tiotropium_refill.txt     ← Track A health refill storyline (CVS path)
      margaret_cardiology_booking_upcoming.txt ← Track A appointment booking storyline (Cal path)
      robert_pt_transport_with_window.txt ← Track A scheduling storyline (schedule payload target)
      dorothy_instacart_cart.txt       ← Track A grocery storyline (Instacart path)
      dorothy_amazon_household_order.txt ← Track A grocery storyline (Amazon path)
      dorothy_missed_metformin.txt     ← POST /patients/pt_003/update/file → health
      margaret_cardiology_overdue.txt  ← POST /patients/pt_001/update/file → appointment
      robert_pge_anomaly.txt           ← POST /patients/pt_002/update/file → financial
      robert_pt_transport.txt          ← POST /patients/pt_002/update/file → scheduling
      dorothy_grocery_reorder.txt      ← POST /patients/pt_003/update/file → grocery
```
