## ADDED Requirements

### Requirement: POST /ingest/file accepts PDF or image and extracts patient record
The endpoint SHALL accept a multipart/form-data upload with fields `file` (UploadFile) and optional `patient_id` (str). For PDF files (content-type `application/pdf`) it SHALL extract text using pdfplumber (all pages joined with newlines). For image files (`image/jpeg`, `image/png`, `image/webp`) it SHALL base64-encode the bytes and call `call_claude_vision` with an extraction prompt. The extracted text SHALL be fed through the same LLM extraction prompt as `/ingest/text`. It SHALL then call `write_patient()` and POST `/internal/detect` with `trigger="patient_create"`. If pdfplumber is not installed, PDF uploads SHALL return HTTP 501.

#### Scenario: PDF upload creates patient
- **WHEN** `POST /ingest/file` receives a multipart PDF with patient data
- **THEN** pdfplumber extracts the text, LLM parses a patient record, patient is written to DB, and `/internal/detect` is called with `patient_create`

#### Scenario: image upload creates patient via vision
- **WHEN** `POST /ingest/file` receives a JPEG image of a patient intake form
- **THEN** `call_claude_vision` extracts the text, LLM parses a patient record, patient is written to DB, and `/internal/detect` is called with `patient_create`

#### Scenario: unsupported file type returns 415
- **WHEN** `POST /ingest/file` receives a `.docx` file
- **THEN** the endpoint returns HTTP 415 Unsupported Media Type

#### Scenario: pdfplumber missing returns 501 for PDF
- **WHEN** pdfplumber is not installed and a PDF is uploaded
- **THEN** the endpoint returns HTTP 501 with `{ "error": "pdf_extraction_unavailable" }`
