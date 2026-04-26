import { useEffect, useRef, useState, type ChangeEvent, type CSSProperties } from "react";
import {
  useGetActionsQuery,
  useGetPatientsQuery,
  useGetPatientQuery,
  useGetUpdateHistoryQuery,
  useIngestTextMutation,
  useIngestFileMutation,
  useSubmitPatientUpdateMutation,
  useConfirmPatientUpdateMutation,
} from "../api/client";
import PatientOverviewByDomain from "../components/PatientOverviewByDomain";
import type { Patient, PatientUpdate } from "../types";
import { urgencyDisplayLabel } from "../utils/urgencyLabels";
import { formatLocal } from "../utils/formatActionDate";

// ── Urgency pill ─────────────────────────────────────────────────────────────

function UrgencyPill({ level }: { level: string | null | undefined }) {
  if (!level) return null;
  const colors: Record<string, { bg: string; text: string }> = {
    tier_0: { bg: "#ffe4e6", text: "#9f1239" },
    tier_1: { bg: "#fef2f2", text: "#991b1b" },
    tier_2: { bg: "#fffbeb", text: "#92400e" },
    tier_3: { bg: "#ecfdf5", text: "#065f46" },
    high: { bg: "#fef2f2", text: "#991b1b" },
    medium: { bg: "#fffbeb", text: "#92400e" },
    low: { bg: "#ecfdf5", text: "#065f46" },
  };
  const c = colors[level] ?? { bg: "#f3f4f6", text: "#374151" };
  return (
    <span style={{ backgroundColor: c.bg, color: c.text, padding: "1px 6px", borderRadius: "9999px", fontSize: "0.7rem", fontWeight: 600 }}>
      {urgencyDisplayLabel(level)}
    </span>
  );
}

// ── Add Patient Modal (glassy iOS-style; aligns with #e8eaed shell + system stack) ─

const addModalScrim: CSSProperties = {
  position: "fixed",
  inset: 0,
  zIndex: 60,
  background: "rgba(15, 23, 42, 0.28)",
  WebkitBackdropFilter: "blur(6px) saturate(120%)",
  backdropFilter: "blur(6px) saturate(120%)",
};

const addModalPanel: CSSProperties = {
  position: "fixed",
  top: "50%",
  left: "50%",
  transform: "translate(-50%, -50%)",
  zIndex: 70,
  width: "min(500px, 96vw)",
  maxHeight: "min(90vh, 640px)",
  display: "flex",
  flexDirection: "column",
  overflow: "hidden",
  borderRadius: 20,
  background: "rgba(255, 255, 255, 0.72)",
  WebkitBackdropFilter: "blur(24px) saturate(180%)",
  backdropFilter: "blur(24px) saturate(180%)",
  border: "1px solid rgba(255, 255, 255, 0.7)",
  boxShadow: "0 25px 50px -12px rgba(15, 23, 42, 0.2), 0 0 0 1px rgba(255,255,255,0.5) inset, inset 0 1px 0 rgba(255,255,255,0.9)",
};

/** Inline glass panel (patient update tab, etc.) — same language as `AddPatientModal` */
const glassPanelInline: CSSProperties = {
  borderRadius: 18,
  overflow: "hidden",
  border: "1px solid rgba(255, 255, 255, 0.65)",
  background: "rgba(255, 255, 255, 0.55)",
  WebkitBackdropFilter: "blur(20px) saturate(170%)",
  backdropFilter: "blur(20px) saturate(170%)",
  boxShadow: "0 14px 36px -14px rgba(15, 23, 42, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.9)",
  width: "100%",
  maxWidth: "100%",
  boxSizing: "border-box",
};

function AddPatientModal({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<"text" | "file">("text");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [ingestText, { isLoading: textLoading }] = useIngestTextMutation();
  const [ingestFile, { isLoading: fileLoading }] = useIngestFileMutation();

  const handleSubmit = async () => {
    if (tab === "text" && text.trim()) {
      await ingestText({ content: text.trim() });
      onClose();
    } else if (tab === "file" && file) {
      await ingestFile({ file });
      onClose();
    }
  };

  const loading = textLoading || fileLoading;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <>
      <div onClick={onClose} style={addModalScrim} aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-patient-title"
        onClick={(e) => e.stopPropagation()}
        style={addModalPanel}
      >
        <div
          style={{
            padding: "1.1rem 1.35rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid rgba(15, 23, 42, 0.06)",
            background: "linear-gradient(180deg, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0.2) 100%)",
          }}
        >
          <div>
            <h2
              id="add-patient-title"
              style={{
                margin: 0,
                fontSize: "1.05rem",
                fontWeight: 600,
                letterSpacing: "-0.02em",
                color: "#0f172a",
                fontFamily: "inherit",
              }}
            >
              Add patient
            </h2>
            <p style={{ margin: "0.2rem 0 0", fontSize: "0.72rem", fontWeight: 500, color: "rgba(15, 23, 42, 0.45)", letterSpacing: "0.04em" }}>
              INGEST FROM TEXT OR FILE
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              width: 32,
              height: 32,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: "none",
              borderRadius: "9999px",
              cursor: "pointer",
              fontSize: "1.15rem",
              lineHeight: 1,
              color: "rgba(15, 23, 42, 0.45)",
              background: "rgba(15, 23, 42, 0.05)",
            }}
          >
            ×
          </button>
        </div>
        <div style={{ padding: "1.15rem 1.35rem 0.5rem", flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
          <div
            style={{
              display: "flex",
              padding: 3,
              marginBottom: "0.9rem",
              background: "rgba(15, 23, 42, 0.05)",
              borderRadius: 12,
              boxSizing: "border-box" as const,
            }}
            role="tablist"
          >
            {(["text", "file"] as const).map((t) => {
              const active = tab === t;
              return (
                <button
                  key={t}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => setTab(t)}
                  style={{
                    flex: 1,
                    padding: "0.45rem 0.6rem",
                    border: "none",
                    borderRadius: 9,
                    cursor: "pointer",
                    fontWeight: 600,
                    fontSize: "0.8125rem",
                    fontFamily: "inherit",
                    color: active ? "#1d4ed8" : "rgba(15, 23, 42, 0.45)",
                    background: active ? "rgba(255, 255, 255, 0.88)" : "transparent",
                    boxShadow: active ? "0 1px 3px rgba(15, 23, 42, 0.08), 0 0 0 1px rgba(255,255,255,0.8) inset" : "none",
                    transition: "color 0.12s ease, background 0.12s ease, box-shadow 0.12s ease",
                  }}
                >
                  {t === "text" ? "Text ingest" : "File upload"}
                </button>
              );
            })}
          </div>

          {tab === "text" ? (
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste or type patient notes, medications, contacts…"
              rows={6}
              style={{
                width: "100%",
                minHeight: "9rem",
                resize: "vertical",
                boxSizing: "border-box" as const,
                border: "1px solid rgba(15, 23, 42, 0.08)",
                borderRadius: 12,
                padding: "0.65rem 0.75rem",
                fontSize: "0.875rem",
                lineHeight: 1.5,
                fontFamily: "inherit",
                color: "#0f172a",
                background: "rgba(255, 255, 255, 0.5)",
                outline: "none",
                boxShadow: "inset 0 1px 1px rgba(15, 23, 42, 0.04)",
              }}
            />
          ) : (
            <label
              style={{
                display: "block",
                padding: "1.1rem 1rem",
                borderRadius: 12,
                border: "1px dashed rgba(15, 23, 42, 0.12)",
                background: "rgba(255, 255, 255, 0.4)",
                cursor: "pointer",
                textAlign: "center",
                fontSize: "0.8rem",
                color: "rgba(15, 23, 42, 0.55)",
              }}
            >
              <input
                type="file"
                accept=".pdf,.png,.jpg,.jpeg"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                style={{ display: "none" }}
              />
              <span style={{ display: "block", fontWeight: 600, color: "#1d4ed8", marginBottom: "0.25rem" }}>Choose file</span>
              PDF, PNG, or JPEG
              {file ? (
                <span style={{ display: "block", marginTop: "0.5rem", fontSize: "0.75rem", color: "#0f172a", fontWeight: 500 }}>{file.name}</span>
              ) : null}
            </label>
          )}
        </div>
        <div
          style={{
            padding: "0.9rem 1.35rem 1.1rem",
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            gap: "0.5rem",
            borderTop: "1px solid rgba(15, 23, 42, 0.06)",
            background: "rgba(232, 234, 237, 0.35)",
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "0.5rem 1rem",
              border: "1px solid rgba(15, 23, 42, 0.12)",
              borderRadius: 9999,
              background: "rgba(255, 255, 255, 0.6)",
              cursor: "pointer",
              fontSize: "0.8125rem",
              fontWeight: 600,
              color: "rgba(15, 23, 42, 0.7)",
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={loading || (tab === "text" ? !text.trim() : !file)}
            style={{
              padding: "0.5rem 1.15rem",
              border: "none",
              borderRadius: 9999,
              background: loading ? "rgba(59, 130, 246, 0.4)" : "#3b82f6",
              color: "#fff",
              cursor: loading ? "not-allowed" : "pointer",
              fontSize: "0.8125rem",
              fontWeight: 600,
              fontFamily: "inherit",
              boxShadow: "0 2px 8px rgba(37, 99, 235, 0.25)",
              opacity: loading || (tab === "text" ? !text.trim() : !file) ? 0.55 : 1,
            }}
          >
            {loading ? "Adding…" : "Add patient"}
          </button>
        </div>
      </div>
    </>
  );
}

// ── Patient update state machine (task 4.6) ───────────────────────────────────

type UpdateState = "idle" | "submitting" | "awaiting_confirmation" | "confirmed" | "cancelled";

function PatientUpdateWidget({ patientId }: { patientId: string }) {
  const [state, setState] = useState<UpdateState>("idle");
  const [updateText, setUpdateText] = useState("");
  const [pendingUpdate, setPendingUpdate] = useState<PatientUpdate | null>(null);
  const [stagedFile, setStagedFile] = useState<File | null>(null);
  const [inlineError, setInlineError] = useState<string | null>(null);
  const [flowBusy, setFlowBusy] = useState(false);
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const [submitUpdate] = useSubmitPatientUpdateMutation();
  const [confirmUpdate, { isLoading: confirming }] = useConfirmPatientUpdateMutation();
  const [ingestFile] = useIngestFileMutation();

  const handleSubmit = async () => {
    const hasText = Boolean(updateText.trim());
    const hasFile = Boolean(stagedFile);
    if (!hasText && !hasFile) return;
    setInlineError(null);
    setFlowBusy(true);
    setState("submitting");
    try {
      if (stagedFile) {
        await ingestFile({
          file: stagedFile,
          patientId,
          context: "This upload applies to the active patient. Merge into their existing record.",
        }).unwrap();
        setStagedFile(null);
      }
      if (hasText) {
        const result = await submitUpdate({ patientId, content: updateText.trim() });
        if ("data" in result && result.data) {
          setPendingUpdate(result.data);
          setState("awaiting_confirmation");
          return;
        }
        setState("idle");
        return;
      }
      setState("confirmed");
    } catch (err: unknown) {
      let msg = "Submit failed";
      if (err && typeof err === "object" && "data" in err) {
        const d = (err as { data?: { error?: string; detail?: string } }).data;
        msg = d?.error || d?.detail || msg;
      } else if (err instanceof Error) msg = err.message;
      setInlineError(msg);
      setState("idle");
    } finally {
      setFlowBusy(false);
    }
  };

  const handleConfirm = async () => {
    if (!pendingUpdate) return;
    await confirmUpdate({ patientId, updateId: pendingUpdate.update_id });
    setState("confirmed");
  };

  const handleCancel = () => {
    setPendingUpdate(null);
    setUpdateText("");
    setStagedFile(null);
    setState("cancelled");
    setTimeout(() => setState("idle"), 1000);
  };

  const handleUploadRecord = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setStagedFile(file);
    setInlineError(null);
  };

  const handlePickUpload = () => uploadInputRef.current?.click();

  const canSubmit = Boolean(updateText.trim() || stagedFile);

  if (state === "confirmed") {
    return (
      <div
        style={{
          ...glassPanelInline,
          padding: "1rem 1.15rem",
          border: "1px solid rgba(16, 185, 129, 0.25)",
          background: "rgba(236, 253, 245, 0.65)",
        }}
      >
        <p style={{ margin: 0, color: "#047857", fontSize: "0.9rem", fontWeight: 600, letterSpacing: "-0.01em" }}>Update saved to the record.</p>
        <p style={{ margin: "0.35rem 0 0", fontSize: "0.78rem", color: "rgba(15, 23, 42, 0.5)" }}>The patient profile will reflect this change on the next refresh.</p>
      </div>
    );
  }

  if (state === "awaiting_confirmation" && pendingUpdate) {
    return (
      <div
        style={{
          ...glassPanelInline,
          border: "1px solid rgba(245, 158, 11, 0.28)",
          background: "rgba(255, 251, 235, 0.6)",
        }}
      >
        <div
          style={{
            padding: "0.85rem 1rem 0.6rem",
            borderBottom: "1px solid rgba(15, 23, 42, 0.06)",
            background: "linear-gradient(180deg, rgba(255,255,255,0.45) 0%, transparent 100%)",
          }}
        >
          <p style={{ margin: 0, fontSize: "0.68rem", fontWeight: 600, letterSpacing: "0.1em", color: "rgba(15, 23, 42, 0.45)" }}>REVIEW BEFORE APPLYING</p>
          <h3 style={{ margin: "0.35rem 0 0", fontSize: "0.95rem", fontWeight: 600, letterSpacing: "-0.02em", color: "#0f172a" }}>Confirm proposed changes</h3>
        </div>
        <div style={{ padding: "0.75rem 1rem" }}>
          <pre
            style={{
              fontSize: "0.78rem",
              whiteSpace: "pre-wrap",
              margin: 0,
              color: "#0f172a",
              lineHeight: 1.45,
              maxHeight: "220px",
              overflow: "auto",
              padding: "0.6rem 0.65rem",
              borderRadius: 12,
              background: "rgba(255, 255, 255, 0.55)",
              border: "1px solid rgba(15, 23, 42, 0.06)",
              boxShadow: "inset 0 1px 1px rgba(15, 23, 42, 0.04)",
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            }}
          >
            {JSON.stringify(pendingUpdate.proposed_changes ?? pendingUpdate, null, 2)}
          </pre>
        </div>
        <div
          style={{
            padding: "0.75rem 1rem 0.95rem",
            display: "flex",
            flexWrap: "wrap",
            gap: "0.5rem",
            justifyContent: "flex-end",
            background: "rgba(232, 234, 237, 0.35)",
            borderTop: "1px solid rgba(15, 23, 42, 0.06)",
          }}
        >
          <button
            type="button"
            onClick={handleCancel}
            style={{
              padding: "0.45rem 1rem",
              border: "1px solid rgba(15, 23, 42, 0.12)",
              borderRadius: 9999,
              background: "rgba(255, 255, 255, 0.65)",
              cursor: "pointer",
              fontSize: "0.8125rem",
              fontWeight: 600,
              color: "rgba(15, 23, 42, 0.75)",
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={confirming}
            style={{
              padding: "0.45rem 1.1rem",
              border: "none",
              borderRadius: 9999,
              background: confirming ? "rgba(16, 185, 129, 0.5)" : "#10b981",
              color: "#fff",
              cursor: confirming ? "not-allowed" : "pointer",
              fontSize: "0.8125rem",
              fontWeight: 600,
              fontFamily: "inherit",
              boxShadow: "0 2px 8px rgba(5, 150, 105, 0.25)",
            }}
          >
            {confirming ? "Confirming…" : "Confirm changes"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={glassPanelInline}>
      <div
        style={{
          padding: "0.75rem 1rem 0.5rem",
          borderBottom: "1px solid rgba(15, 23, 42, 0.05)",
          background: "linear-gradient(180deg, rgba(255,255,255,0.5) 0%, transparent 100%)",
        }}
      >
        <p style={{ margin: 0, fontSize: "0.68rem", fontWeight: 600, letterSpacing: "0.1em", color: "rgba(15, 23, 42, 0.45)" }}>PATIENT UPDATE</p>
        <h3 style={{ margin: "0.3rem 0 0", fontSize: "0.95rem", fontWeight: 600, letterSpacing: "-0.02em", color: "#0f172a" }}>Add a note to the record</h3>
      </div>
      {stagedFile && (
        <div
          style={{
            padding: "0.5rem 1rem",
            borderBottom: "1px solid rgba(59, 130, 246, 0.12)",
            background: "rgba(239, 246, 255, 0.5)",
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: "0.5rem 0.75rem",
            justifyContent: "space-between",
          }}
        >
          <p style={{ margin: 0, fontSize: "0.8rem", lineHeight: 1.45, color: "rgba(15, 23, 42, 0.8)" }}>
            <strong>File staged:</strong> {stagedFile.name}. It will be sent with this update. Add a note if you like, then click <strong>Submit update</strong> to process the record.
          </p>
          <button
            type="button"
            onClick={() => { setStagedFile(null); setInlineError(null); }}
            style={{
              padding: "0.25rem 0.6rem",
              fontSize: "0.75rem",
              fontWeight: 600,
              color: "rgba(15, 23, 42, 0.7)",
              background: "rgba(255,255,255,0.75)",
              border: "1px solid rgba(15, 23, 42, 0.12)",
              borderRadius: 8,
              cursor: "pointer",
            }}
          >
            Remove file
          </button>
        </div>
      )}
      {inlineError && (
        <div style={{ padding: "0.45rem 1rem 0", borderBottom: "1px solid rgba(220, 38, 38, 0.12)" }}>
          <p style={{ margin: 0, fontSize: "0.8rem", color: "#b91c1c" }}>{inlineError}</p>
        </div>
      )}
      <div style={{ padding: "0.75rem 1rem 0.4rem" }}>
        <textarea
          id={`patient-update-${patientId}`}
          aria-label="Patient update note"
          value={updateText}
          onChange={(e) => setUpdateText(e.target.value)}
          placeholder="Describe the update — medications, visits, preferences, or other clinical notes…"
          rows={5}
          style={{
            width: "100%",
            minHeight: "7.5rem",
            resize: "vertical",
            boxSizing: "border-box" as const,
            border: "1px solid rgba(15, 23, 42, 0.08)",
            borderRadius: 12,
            padding: "0.65rem 0.75rem",
            fontSize: "0.875rem",
            lineHeight: 1.5,
            fontFamily: "inherit",
            color: "#0f172a",
            background: "rgba(255, 255, 255, 0.5)",
            outline: "none",
            boxShadow: "inset 0 1px 1px rgba(15, 23, 42, 0.04)",
          }}
        />
      </div>
      <div
        style={{
          padding: "0.7rem 1rem 0.9rem",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "flex-end",
          gap: "0.5rem",
          background: "rgba(232, 234, 237, 0.35)",
          borderTop: "1px solid rgba(15, 23, 42, 0.06)",
        }}
      >
        <input
          ref={uploadInputRef}
          type="file"
          style={{ position: "absolute", width: 1, height: 1, margin: -1, padding: 0, overflow: "hidden", clip: "rect(0,0,0,0)", border: 0 }}
          accept=".txt,.pdf,.png,.jpg,.jpeg,.webp"
          onChange={handleUploadRecord}
          aria-label="Upload a record file for ingest"
        />
        <button
          type="button"
          onClick={handlePickUpload}
          disabled={flowBusy}
          style={{
            padding: "0.5rem 1.15rem",
            border: "1px solid rgba(15, 23, 42, 0.14)",
            borderRadius: 9999,
            background: "rgba(255, 255, 255, 0.7)",
            color: "rgba(15, 23, 42, 0.85)",
            cursor: flowBusy ? "not-allowed" : "pointer",
            fontSize: "0.8125rem",
            fontWeight: 600,
            fontFamily: "inherit",
            boxShadow: "0 1px 4px rgba(15, 23, 42, 0.06), inset 0 1px 0 rgba(255,255,255,0.95)",
            opacity: flowBusy ? 0.7 : 1,
          }}
        >
          {stagedFile ? "Change file" : "Upload record"}
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit || flowBusy}
          style={{
            padding: "0.5rem 1.15rem",
            border: "none",
            borderRadius: 9999,
            background: !canSubmit || flowBusy ? "rgba(59, 130, 246, 0.4)" : "#3b82f6",
            color: "#fff",
            cursor: !canSubmit || flowBusy ? "not-allowed" : "pointer",
            fontSize: "0.8125rem",
            fontWeight: 600,
            fontFamily: "inherit",
            boxShadow: "0 2px 8px rgba(37, 99, 235, 0.25)",
            opacity: !canSubmit || flowBusy ? 0.6 : 1,
          }}
        >
          {flowBusy ? "Submitting…" : "Submit update"}
        </button>
      </div>
    </div>
  );
}

// ── Update History tab (task 4.7) ─────────────────────────────────────────────

function UpdateHistoryPanel({ patientId }: { patientId: string }) {
  const { data: history = [], isLoading } = useGetUpdateHistoryQuery(patientId);
  if (isLoading) return <p style={{ fontSize: "0.85rem", color: "#6b7280" }}>Loading history…</p>;
  if (history.length === 0) {
    return (
      <div style={{ fontSize: "0.85rem", color: "#6b7280", lineHeight: 1.5, maxWidth: "40rem" }}>
        <p style={{ margin: "0 0 0.5rem" }}>No update history yet.</p>
        <p style={{ margin: 0, color: "#9ca3af", fontSize: "0.8rem" }}>
          After the next <strong style={{ color: "#6b7280" }}>ingest</strong> (text or file) or a staged <strong>Update</strong> (submit → confirm), entries appear here. New <strong>actions</strong> from detection still show on the action feed and patient overview.
        </p>
      </div>
    );
  }
  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      {history.map((u) => (
        <li key={u.update_id} style={{ border: "1px solid #e5e7eb", borderRadius: "6px", padding: "0.5rem 0.75rem", fontSize: "0.8rem" }}>
          <div style={{ display: "flex", gap: "0.75rem", marginBottom: "0.25rem", flexWrap: "wrap", alignItems: "center" }}>
            <span style={{ color: "#6b7280" }}>{formatLocal(u.submitted_at)}</span>
            {u.fromIngest && (
              <span
                style={{
                  fontSize: "0.65rem",
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase" as const,
                  color: "#0369a1",
                  background: "rgba(7, 89, 133, 0.1)",
                  padding: "2px 8px",
                  borderRadius: 9999,
                }}
              >
                Intake
              </span>
            )}
            {u.domain && <span style={{ fontWeight: 500 }}>{u.domain}</span>}
            <span style={{ marginLeft: "auto", color: u.status === "confirmed" ? "#065f46" : u.status === "cancelled" ? "#991b1b" : "#92400e" }}>
              {u.fromIngest && u.status === "confirmed" ? "Logged" : u.status === "confirmed" ? "Applied" : u.status}
            </span>
          </div>
          {u.summary && <p style={{ margin: 0, color: "#374151" }}>{u.summary}</p>}
        </li>
      ))}
    </ul>
  );
}

// ── Patient Detail Panel ──────────────────────────────────────────────────────

type DetailTab = "overview" | "update" | "history";

function PatientDetailPanel({ patientId }: { patientId: string }) {
  const [tab, setTab] = useState<DetailTab>("overview");
  const { data: patient, isLoading } = useGetPatientQuery(patientId);
  const { data: feedActions = [] } = useGetActionsQuery({ sort: "rank" }, { pollingInterval: 10_000 });

  if (isLoading) return <div style={{ padding: "1.5rem", color: "#6b7280" }}>Loading…</div>;
  if (!patient) return <div style={{ padding: "1.5rem", color: "#6b7280" }}>Patient not found.</div>;

  return (
    <div style={{ padding: "1.25rem", overflowY: "auto", height: "100%" }}>
      <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem", fontWeight: 700 }}>{patient.name}</h2>

      {/* Tab bar */}
      <div style={{ display: "flex", gap: 0, borderBottom: "1px solid #e5e7eb", marginBottom: "1rem" }}>
        {(["overview", "update", "history"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "0.5rem 1rem",
              border: "none",
              borderBottom: tab === t ? "2px solid #3b82f6" : "2px solid transparent",
              background: "none",
              cursor: "pointer",
              fontWeight: tab === t ? 600 : 400,
              color: tab === t ? "#3b82f6" : "#374151",
              fontSize: "0.875rem",
            }}
          >
            {t === "overview" ? "Overview" : t === "update" ? "Update" : "Update History"}
          </button>
        ))}
      </div>

      {tab === "overview" && <PatientOverviewByDomain patient={patient} feedActions={feedActions} />}

      {tab === "update" && <PatientUpdateWidget patientId={patientId} />}
      {tab === "history" && <UpdateHistoryPanel patientId={patientId} />}
    </div>
  );
}

// ── Main view ─────────────────────────────────────────────────────────────────

export default function PatientRoster() {
  const { data: patients = [], isLoading } = useGetPatientsQuery();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);

  return (
    <div style={{ display: "flex", height: "calc(100vh - 56px)" }}>
      {/* Sidebar (tasks 4.1, 4.2) */}
      <aside
        style={{
          width: "280px",
          borderRight: "1px solid #d1d5db",
          display: "flex",
          flexDirection: "column",
          flexShrink: 0,
          background: "#e8eaed",
        }}
      >
        <div
          style={{
            padding: "1rem",
            borderBottom: "1px solid #d1d5db",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            background: "#e8eaed",
          }}
        >
          <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>Patients</span>
          <button
            onClick={() => setAddOpen(true)}
            style={{ padding: "0.3rem 0.75rem", backgroundColor: "#3b82f6", color: "#fff", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "0.8rem", fontWeight: 500 }}
          >
            + Add
          </button>
        </div>
        <div style={{ overflowY: "auto", flex: 1, background: "#e8eaed" }}>
          {isLoading && <p style={{ padding: "1rem", color: "#6b7280", fontSize: "0.85rem" }}>Loading…</p>}
          {patients.map((p) => (
            <button
              key={p.patient_id}
              onClick={() => setSelectedId(p.patient_id)}
              style={{
                display: "block",
                width: "100%",
                padding: "0.75rem 1rem",
                textAlign: "left",
                border: "none",
                borderBottom: "1px solid rgba(0, 0, 0, 0.06)",
                background: selectedId === p.patient_id ? "rgba(59, 130, 246, 0.08)" : "transparent",
                cursor: "pointer",
              }}
            >
              <div style={{ fontWeight: 500, fontSize: "0.875rem", marginBottom: "0.25rem" }}>{p.name}</div>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                {p.pending_action_count !== undefined && (
                  <span style={{ fontSize: "0.75rem", color: "#6b7280" }}>{p.pending_action_count} pending</span>
                )}
                <UrgencyPill level={p.highest_urgency_level} />
              </div>
            </button>
          ))}
        </div>
      </aside>

      {/* Detail panel */}
      <div style={{ flex: 1, overflow: "hidden" }}>
        {selectedId ? (
          <PatientDetailPanel patientId={selectedId} />
        ) : (
          <div style={{ padding: "2rem", color: "#9ca3af" }}>Select a patient to view details.</div>
        )}
      </div>

      {addOpen && <AddPatientModal onClose={() => setAddOpen(false)} />}
    </div>
  );
}
