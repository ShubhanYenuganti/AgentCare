# Test Cases — Ingest & Pipeline Gaps

**Assumed defaults:**
- FastAPI API server: `http://localhost:8000`
- Executor REST (uagents): `http://localhost:8001`
- Executor ASI:One address: set `EXECUTOR_AGENT_ADDRESS` env var; retrieve it at runtime via `python -c "from agents.shared.config import EXECUTOR_ADDRESS; print(EXECUTOR_ADDRESS)"`

---

## 1. `POST /ingest/text` — natural-language patient onboarding

### 1a. New patient onboarding from free-form text
```bash
curl -s -X POST http://localhost:8000/ingest/text \
  -H "Content-Type: application/json" \
  -d '{
    "content": "New patient: Margaret Chen, age 72, lives at 12 Oak Avenue, San Francisco CA 94102. Primary physician Dr. Sarah Kim at SF Medical Center (sfmed@example.com). Current medications: Lisinopril 10mg once daily (pharmacy: Walgreens, walgreens@example.com). Emergency contact: daughter Amy Chen, 415-555-0120. Dietary restrictions: low sodium. Upcoming cardiology appointment scheduled for next month."
  }' | python3 -m json.tool
```
**Expected:** `{ "success": true, "data": { "patient_id": "...", "extracted": {...}, "detect_status": "triggered" } }`

### 1b. Onboarding with explicit patient_id override
```bash
curl -s -X POST http://localhost:8000/ingest/text \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "pt_test_001",
    "content": "Patient Robert Harris, age 68, 45 Pine Street, Oakland CA. Medications: Warfarin 5mg daily, Aspirin 81mg daily."
  }' | python3 -m json.tool
```
**Expected:** `"patient_id": "pt_test_001"` in response data

### 1c. Unparseable content → 422
```bash
curl -s -X POST http://localhost:8000/ingest/text \
  -H "Content-Type: application/json" \
  -d '{"content": "hello world this is not patient data"}' | python3 -m json.tool
```
**Expected:** HTTP 422, `{ "success": false, "error": "extraction_failed", "raw": "..." }`

### 1d. Verify patient was written to DB
```bash
curl -s http://localhost:8000/patients | python3 -m json.tool
```
Confirm the new patient appears in the list.

---

## 2. `POST /ingest/file` — file-based patient onboarding

### 2a. PDF upload
```bash
# Create a sample patient PDF text file first
echo "Patient Intake Form
Name: Dorothy Kim
Age: 80
Address: 78 Maple Drive, Berkeley CA 94710
Primary Doctor: Dr. James Park
Medications: Metformin 500mg twice daily
Emergency Contact: son Kevin Kim, 510-555-0199" > /tmp/patient_intake.txt

# Convert to PDF using built-in tools (macOS)
cupsfilter /tmp/patient_intake.txt > /tmp/patient_intake.pdf 2>/dev/null || \
  echo "Use an existing PDF file if cupsfilter unavailable"

curl -s -X POST http://localhost:8000/ingest/file \
  -F "file=@/tmp/patient_intake.pdf;type=application/pdf" | python3 -m json.tool
```

### 2b. JPEG image upload
```bash
curl -s -X POST http://localhost:8000/ingest/file \
  -F "file=@/path/to/intake_form.jpg;type=image/jpeg" \
  -F "patient_id=pt_img_001" | python3 -m json.tool
```

### 2c. Unsupported file type → 415
```bash
echo "test" > /tmp/test.docx
curl -s -X POST http://localhost:8000/ingest/file \
  -F "file=@/tmp/test.docx;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document" \
  -o - -w "\nHTTP %{http_code}\n"
```
**Expected:** HTTP 415

---

## 3. `POST /patients/{id}/update` — staged patient update

### 3a. Propose a medication update
```bash
curl -s -X POST http://localhost:8000/patients/pt_001/update \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Margaret Chen'\''s Lisinopril dose has been increased to 20mg per day starting today per Dr. Kim'\''s orders. Pharmacy notified.",
    "caregiver_id": "cg_001"
  }' | python3 -m json.tool
```
**Expected:**
```json
{
  "success": true,
  "data": {
    "requires_confirmation": true,
    "update_id": 1,
    "classification": {
      "domain": "health",
      "operation": "update",
      "fields_changed": ["medications"],
      "summary": "Lisinopril dose increased to 20mg",
      "proposed_changes": { "medications": [...] }
    }
  }
}
```

### 3b. Propose adding a new appointment
```bash
curl -s -X POST http://localhost:8000/patients/pt_001/update \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Scheduled Margaret for a new neurology appointment with Dr. Patel at UCSF on June 15, 2026."
  }' | python3 -m json.tool
```

### 3c. Unknown patient → 404
```bash
curl -s -X POST http://localhost:8000/patients/pt_999/update \
  -H "Content-Type: application/json" \
  -d '{"content": "Update for nonexistent patient"}' \
  -o - -w "\nHTTP %{http_code}\n"
```

---

## 4. `POST /patients/{id}/update/{update_id}/confirm` — apply staged update

### 4a. Confirm and apply a staged update
```bash
# First get the update_id from the POST /update response above (e.g. 1)
curl -s -X POST http://localhost:8000/patients/pt_001/update/1/confirm \
  | python3 -m json.tool
```
**Expected:**
```json
{
  "success": true,
  "data": {
    "applied": true,
    "patient_id": "pt_001",
    "update_id": 1,
    "detect_status": "triggered"
  }
}
```

### 4b. Double-confirm → 409
```bash
curl -s -X POST http://localhost:8000/patients/pt_001/update/1/confirm \
  -o - -w "\nHTTP %{http_code}\n"
```
**Expected:** HTTP 409

---

## 5. `POST /patients/{id}/update/file` — staged update from file

### 5a. PDF lab report update
```bash
echo "Lab results for patient pt_001: HbA1c 7.2%, eGFR 58 (stage 3 CKD). Recommend increasing monitoring frequency." > /tmp/lab_report.txt
# Convert to PDF or use an existing PDF
curl -s -X POST http://localhost:8000/patients/pt_001/update/file \
  -F "file=@/tmp/lab_report.pdf;type=application/pdf" \
  -F "caregiver_id=cg_001" | python3 -m json.tool
```

---

## 6. `GET /patients/{id}/update-history`

```bash
curl -s http://localhost:8000/patients/pt_001/update-history | python3 -m json.tool
```
**Expected:** Array of update records ordered newest-first with `id`, `domain`, `operation`, `fields_changed`, `summary`, `confirmed`, `applied`, `created_at`.

---

## 7. `POST /actions/{id}/chat` — action-bound chat

### 7a. Send a chat message to an action
```bash
# First get an action_id from the actions list
curl -s http://localhost:8000/actions | python3 -m json.tool

# Then send a chat message (replace act_XXX with a real action_id)
curl -s -X POST http://localhost:8000/actions/act_seed_overdue_001/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Can you explain what triggered this alert and what I should do?"}' \
  | python3 -m json.tool
```
**Expected:** `{ "success": true, "data": { "status": "queued", "chat_id": 1 } }`

### 7b. Chat on unknown action → 404
```bash
curl -s -X POST http://localhost:8000/actions/act_nonexistent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}' \
  -o - -w "\nHTTP %{http_code}\n"
```

---

## 8. `GET /actions/{id}/chat-history`

```bash
curl -s http://localhost:8000/actions/act_seed_overdue_001/chat-history | python3 -m json.tool
```
**Expected:** Array of `{ id, role, content, intent, created_at }` ordered chronologically.

---

## 9. `POST /actions/{id}/dismiss`

```bash
curl -s -X POST http://localhost:8000/actions/act_seed_overdue_001/dismiss | python3 -m json.tool
```
**Expected:** Updated action with `completed=1`, `reviewed=1`, `outcome="dismissed"`, `completion_date` set.

---

## 10. `POST /actions/{id}/approve` — verify completion metadata

```bash
curl -s -X POST http://localhost:8000/actions/act_seed_overdue_001/approve | python3 -m json.tool
```
**Expected on success:** Action has `outcome="approved"` and `completion_date` set to ISO datetime string.

---

## 11. ASI:One Tests — Natural Language against Executor Agent

> **Setup:** In ASI:One (app.fetch.ai), open a chat with the executor agent address.
> Retrieve the address with:
> ```bash
> python3 -c "from agents.shared.config import EXECUTOR_ADDRESS; print(EXECUTOR_ADDRESS)"
> ```
> Paste that address into ASI:One's "Agent Address" field.

### 11a. Natural language patient onboarding (new patient)
Send this message in ASI:One chat:
```
New patient intake: Margaret Chen, age 72, lives at 12 Oak Avenue, San Francisco CA 94102.
Her primary physician is Dr. Sarah Kim at SF Medical Center (sfmed@sfmedical.com, 415-555-1000).
Current medications: Lisinopril 10mg once daily (last refill April 10, 30-day supply), Atorvastatin 20mg at bedtime.
Pharmacy: Walgreens on Market St (walgreens-market@example.com).
Emergency contact: daughter Amy Chen at 415-555-0120.
Upcoming cardiology appointment with Dr. James Lee at UCSF Cardiology on May 15, 2026.
Dietary restrictions: low sodium, no shellfish.
```
**Expected executor response:** Acknowledgement that the patient record is being processed, confirmation of detection fan-out.

### 11b. Natural language update query
```
What is the current refill status for Margaret Chen's Lisinopril?
```
**Expected:** The executor routes as a "question" intent to health domain and responds with the medication refill info from the life graph.

### 11c. Detection trigger via natural language
```
Run a health check for patient pt_001 — she may have missed her last Warfarin dose.
```
**Expected:** Executor classifies as detection/health intent and fans out to the health supervisor.

### 11d. Scheduling intent
```
I need to arrange a caregiver visit for Robert Harris next week for physical therapy transport.
```
**Expected:** Executor classifies as scheduling intent and routes to scheduling agent.

---

## 12. ASI:One Tests — File-Based Ingest

> File uploads must go through the FastAPI HTTP endpoint (`/ingest/file`), not ASI:One chat directly.
> Use this command to test file ingest with a real patient text document:

```bash
# Create a sample patient record as a text file
cat > /tmp/new_patient_intake.txt << 'EOF'
PATIENT INTAKE FORM
-------------------
Name: Thomas Webb
Age: 74
Address: 233 Cedar Street, Palo Alto CA 94301
Primary Physician: Dr. Patricia Nguyen
Clinic: Palo Alto Medical Foundation
Clinic Email: pamf@example.com
Clinic Phone: 650-555-8800

MEDICATIONS:
- Metoprolol 25mg twice daily (pharmacy: CVS Palo Alto, cvs-pa@example.com)
- Amlodipine 5mg once daily

EMERGENCY CONTACTS:
- Wife: Helen Webb, 650-555-0234
- Son: Marcus Webb, 650-555-0567

DIETARY RESTRICTIONS: low fat, diabetic diet

APPOINTMENTS:
- Cardiology follow-up: Dr. Robert Chen, Stanford Hospital, every 3 months, last visit Jan 10 2026
EOF

# Submit via API
curl -s -X POST http://localhost:8000/ingest/file \
  -F "file=@/tmp/new_patient_intake.txt;type=text/plain" | python3 -m json.tool
```

> **Note:** ASI:One chat does not support binary file uploads. All file-based ingest must use the `POST /ingest/file` HTTP endpoint above.
