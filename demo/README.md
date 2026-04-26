# Autocare Demo Setup

Three tracks depending on how much you want to see. All start with a fresh SQLite database.

---

## Track A — Instant seed (30 seconds)

Seeds the database with 3 patients, 10 caregivers, and 6 cross-domain action items, then opens the dashboard.

```bash
bash demo/quick_start.sh
```

Open: http://localhost:5173

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
      dorothy_missed_metformin.txt     ← POST /patients/pt_003/update/file → health
      margaret_cardiology_overdue.txt  ← POST /patients/pt_001/update/file → appointment
      robert_pge_anomaly.txt           ← POST /patients/pt_002/update/file → financial
      robert_pt_transport.txt          ← POST /patients/pt_002/update/file → scheduling
      dorothy_grocery_reorder.txt      ← POST /patients/pt_003/update/file → grocery
```
