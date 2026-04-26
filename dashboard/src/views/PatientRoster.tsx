import { useState } from "react";
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

// ── Add Patient Modal ─────────────────────────────────────────────────────────

function AddPatientModal({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<"text" | "file">("text");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [ingestText, { isLoading: textLoading }] = useIngestTextMutation();
  const [ingestFile, { isLoading: fileLoading }] = useIngestFileMutation();

  const handleSubmit = async () => {
    if (tab === "text" && text.trim()) {
      await ingestText(text.trim());
      onClose();
    } else if (tab === "file" && file) {
      const fd = new FormData();
      fd.append("file", file);
      await ingestFile(fd);
      onClose();
    }
  };

  const loading = textLoading || fileLoading;

  return (
    <>
      <div onClick={onClose} style={{ position: "fixed", inset: 0, backgroundColor: "rgba(0,0,0,0.4)", zIndex: 60 }} />
      <div style={{ position: "fixed", top: "50%", left: "50%", transform: "translate(-50%,-50%)", width: "500px", maxWidth: "95vw", backgroundColor: "#fff", borderRadius: "8px", boxShadow: "0 20px 60px rgba(0,0,0,0.2)", zIndex: 70 }}>
        <div style={{ padding: "1.25rem 1.5rem", borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>Add Patient</h2>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1.25rem", color: "#6b7280" }}>×</button>
        </div>
        <div style={{ padding: "1.25rem 1.5rem" }}>
          <div style={{ display: "flex", gap: "0", marginBottom: "1rem", border: "1px solid #d1d5db", borderRadius: "6px", overflow: "hidden" }}>
            {(["text", "file"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                style={{ flex: 1, padding: "0.5rem", border: "none", cursor: "pointer", backgroundColor: tab === t ? "#3b82f6" : "#fff", color: tab === t ? "#fff" : "#374151", fontWeight: 500, fontSize: "0.875rem" }}
              >
                {t === "text" ? "Text Ingest" : "File Upload"}
              </button>
            ))}
          </div>

          {tab === "text" ? (
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Enter patient information as free-form text…"
              rows={6}
              style={{ width: "100%", resize: "vertical", border: "1px solid #d1d5db", borderRadius: "6px", padding: "0.5rem", fontSize: "0.875rem", fontFamily: "inherit", boxSizing: "border-box" }}
            />
          ) : (
            <div>
              <input
                type="file"
                accept=".pdf,.png,.jpg,.jpeg"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                style={{ display: "block", marginBottom: "0.5rem" }}
              />
              {file && <p style={{ fontSize: "0.8rem", color: "#6b7280" }}>Selected: {file.name}</p>}
            </div>
          )}
        </div>
        <div style={{ padding: "1rem 1.5rem", borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
          <button onClick={onClose} style={{ padding: "0.5rem 1rem", border: "1px solid #d1d5db", borderRadius: "6px", background: "#fff", cursor: "pointer", fontSize: "0.875rem" }}>Cancel</button>
          <button
            onClick={handleSubmit}
            disabled={loading || (tab === "text" ? !text.trim() : !file)}
            style={{ padding: "0.5rem 1.25rem", backgroundColor: "#3b82f6", color: "#fff", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "0.875rem", fontWeight: 500, opacity: loading ? 0.6 : 1 }}
          >
            {loading ? "Adding…" : "Add Patient"}
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
  const [submitUpdate, { isLoading: submitting }] = useSubmitPatientUpdateMutation();
  const [confirmUpdate, { isLoading: confirming }] = useConfirmPatientUpdateMutation();

  const handleSubmit = async () => {
    if (!updateText.trim()) return;
    setState("submitting");
    const result = await submitUpdate({ patientId, update_text: updateText.trim() });
    if ("data" in result) {
      setPendingUpdate(result.data);
      setState("awaiting_confirmation");
    } else {
      setState("idle");
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
    setState("cancelled");
    setTimeout(() => setState("idle"), 1000);
  };

  if (state === "confirmed") {
    return <p style={{ color: "#065f46", fontSize: "0.875rem" }}>Update confirmed.</p>;
  }

  if (state === "awaiting_confirmation" && pendingUpdate) {
    return (
      <div style={{ border: "1px solid #f59e0b", borderRadius: "6px", padding: "0.75rem", backgroundColor: "#fffbeb" }}>
        <p style={{ margin: "0 0 0.5rem", fontSize: "0.875rem", fontWeight: 500 }}>Proposed changes:</p>
        <pre style={{ fontSize: "0.8rem", whiteSpace: "pre-wrap", margin: "0 0 0.75rem", color: "#374151" }}>
          {JSON.stringify(pendingUpdate.proposed_changes ?? pendingUpdate, null, 2)}
        </pre>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button onClick={handleConfirm} disabled={confirming} style={{ padding: "0.4rem 0.875rem", backgroundColor: "#10b981", color: "#fff", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "0.8rem" }}>
            {confirming ? "Confirming…" : "Confirm"}
          </button>
          <button onClick={handleCancel} style={{ padding: "0.4rem 0.875rem", backgroundColor: "#ef4444", color: "#fff", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "0.8rem" }}>
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <textarea
        value={updateText}
        onChange={(e) => setUpdateText(e.target.value)}
        placeholder="Describe the update to this patient's record…"
        rows={3}
        style={{ width: "100%", resize: "vertical", border: "1px solid #d1d5db", borderRadius: "6px", padding: "0.5rem", fontSize: "0.875rem", fontFamily: "inherit", boxSizing: "border-box", marginBottom: "0.5rem" }}
      />
      <button
        onClick={handleSubmit}
        disabled={submitting || !updateText.trim()}
        style={{ padding: "0.4rem 0.875rem", backgroundColor: "#3b82f6", color: "#fff", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "0.8rem", fontWeight: 500, opacity: submitting ? 0.6 : 1 }}
      >
        {submitting ? "Submitting…" : "Submit Update"}
      </button>
    </div>
  );
}

// ── Update History tab (task 4.7) ─────────────────────────────────────────────

function UpdateHistoryPanel({ patientId }: { patientId: string }) {
  const { data: history = [], isLoading } = useGetUpdateHistoryQuery(patientId);
  if (isLoading) return <p style={{ fontSize: "0.85rem", color: "#6b7280" }}>Loading history…</p>;
  if (history.length === 0) return <p style={{ fontSize: "0.85rem", color: "#6b7280" }}>No update history.</p>;
  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      {history.map((u) => (
        <li key={u.update_id} style={{ border: "1px solid #e5e7eb", borderRadius: "6px", padding: "0.5rem 0.75rem", fontSize: "0.8rem" }}>
          <div style={{ display: "flex", gap: "0.75rem", marginBottom: "0.25rem" }}>
            <span style={{ color: "#6b7280" }}>{formatLocal(u.submitted_at)}</span>
            {u.domain && <span style={{ fontWeight: 500 }}>{u.domain}</span>}
            <span style={{ marginLeft: "auto", color: u.status === "confirmed" ? "#065f46" : u.status === "cancelled" ? "#991b1b" : "#92400e" }}>{u.status}</span>
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
