import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useUpdateOrgMutation,
  useCreateCaregiverMutation,
  useGetCaregiversQuery,
  useIngestFileMutation,
  useGetPatientsQuery,
} from "../api/client";
import type { CreateCaregiverBody, DaySchedule } from "../types";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;
type Day = (typeof DAYS)[number];

const BG = "#f3f4f6";
const CARD_SHADOW = "0 4px 24px rgba(0,0,0,0.08)";

const STEPS = [
  { n: 1, label: "Organization" },
  { n: 2, label: "Caregivers" },
  { n: 3, label: "Patients" },
  { n: 4, label: "Ready" },
];

// ── Inline caregiver form (no modal overlay; embedded in the step card) ───────

function CaregiverForm({ onAdded }: { onAdded: () => void }) {
  const [createCaregiver, { isLoading }] = useCreateCaregiverMutation();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState<"caregiver" | "admin">("caregiver");
  const [schedule, setSchedule] = useState<Partial<Record<Day, DaySchedule>>>({});
  const [open, setOpen] = useState(false);

  const toggleDay = (day: Day) => {
    setSchedule((prev) => {
      const next = { ...prev };
      if (next[day]) delete next[day];
      else next[day] = { start: "09:00", end: "17:00" };
      return next;
    });
  };

  const setHour = (day: Day, field: "start" | "end", val: string) =>
    setSchedule((prev) => ({ ...prev, [day]: { ...prev[day]!, [field]: val } }));

  const handleSubmit = async () => {
    if (!name.trim() || !email.trim()) return;
    await createCaregiver({ name: name.trim(), email: email.trim(), phone: phone.trim(), role, schedule } as CreateCaregiverBody);
    setName(""); setEmail(""); setPhone(""); setRole("caregiver"); setSchedule({});
    setOpen(false);
    onAdded();
  };

  const canSubmit = name.trim() && email.trim() && !isLoading;

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{ padding: "0.5rem 1.25rem", background: "#3b82f6", color: "#fff", border: "none", borderRadius: 6, fontSize: "0.875rem", fontWeight: 500, cursor: "pointer" }}
      >
        + Add Caregiver
      </button>
    );
  }

  return (
    <div style={{ border: "1px solid #d1d5db", borderRadius: 8, padding: "1.25rem", marginTop: "0.75rem", background: "#fff" }}>
      <p style={{ margin: "0 0 1rem", fontWeight: 600, fontSize: "0.9rem" }}>New Caregiver</p>
      {(["Name", "Email", "Phone"] as const).map((label) => {
        const key = label.toLowerCase() as "name" | "email" | "phone";
        const val = key === "name" ? name : key === "email" ? email : phone;
        const setter = key === "name" ? setName : key === "email" ? setEmail : setPhone;
        return (
          <div key={label} style={{ marginBottom: "0.75rem" }}>
            <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 500, marginBottom: "0.2rem", color: "#374151" }}>{label}</label>
            <input
              type="text" value={val} onChange={(e) => setter(e.target.value)}
              style={{ width: "100%", padding: "0.4rem 0.5rem", border: "1px solid #d1d5db", borderRadius: 6, fontSize: "0.875rem", boxSizing: "border-box" }}
            />
          </div>
        );
      })}
      <div style={{ marginBottom: "1rem" }}>
        <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 500, marginBottom: "0.2rem", color: "#374151" }}>Role</label>
        <select value={role} onChange={(e) => setRole(e.target.value as "caregiver" | "admin")}
          style={{ width: "100%", padding: "0.4rem 0.5rem", border: "1px solid #d1d5db", borderRadius: 6, fontSize: "0.875rem" }}>
          <option value="caregiver">Caregiver</option>
          <option value="admin">Admin</option>
        </select>
      </div>
      <p style={{ fontSize: "0.8rem", fontWeight: 500, margin: "0 0 0.4rem", color: "#374151" }}>Weekly Schedule</p>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem", marginBottom: "1rem" }}>
        <thead>
          <tr style={{ color: "#9ca3af" }}>
            <th style={{ width: 32, textAlign: "left" }}></th>
            <th style={{ width: 50, textAlign: "left" }}>Day</th>
            <th style={{ textAlign: "left" }}>Start</th>
            <th style={{ textAlign: "left" }}>End</th>
          </tr>
        </thead>
        <tbody>
          {DAYS.map((day) => {
            const entry = schedule[day];
            return (
              <tr key={day} style={{ borderTop: "1px solid #f3f4f6" }}>
                <td style={{ padding: "0.3rem 0" }}><input type="checkbox" checked={!!entry} onChange={() => toggleDay(day)} /></td>
                <td style={{ padding: "0.3rem 0", color: entry ? "#111827" : "#9ca3af" }}>{day}</td>
                <td style={{ padding: "0.3rem 0.4rem 0.3rem 0" }}>
                  <input type="text" disabled={!entry} value={entry?.start ?? ""} onChange={(e) => setHour(day, "start", e.target.value)} placeholder="09:00"
                    style={{ width: 64, padding: "0.2rem 0.3rem", border: "1px solid #d1d5db", borderRadius: 4, fontSize: "0.78rem", opacity: entry ? 1 : 0.4 }} />
                </td>
                <td style={{ padding: "0.3rem 0" }}>
                  <input type="text" disabled={!entry} value={entry?.end ?? ""} onChange={(e) => setHour(day, "end", e.target.value)} placeholder="17:00"
                    style={{ width: 64, padding: "0.2rem 0.3rem", border: "1px solid #d1d5db", borderRadius: 4, fontSize: "0.78rem", opacity: entry ? 1 : 0.4 }} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end" }}>
        <button onClick={() => setOpen(false)}
          style={{ padding: "0.45rem 1rem", border: "1px solid #d1d5db", borderRadius: 6, background: "#fff", cursor: "pointer", fontSize: "0.875rem" }}>
          Cancel
        </button>
        <button onClick={handleSubmit} disabled={!canSubmit}
          style={{ padding: "0.45rem 1.25rem", background: canSubmit ? "#3b82f6" : "#d1d5db", color: "#fff", border: "none", borderRadius: 6, cursor: canSubmit ? "pointer" : "not-allowed", fontSize: "0.875rem", fontWeight: 500 }}>
          {isLoading ? "Adding…" : "Save Caregiver"}
        </button>
      </div>
    </div>
  );
}

// ── Step components ───────────────────────────────────────────────────────────

function StepOrg({ onNext }: { onNext: () => void }) {
  const [updateOrg, { isLoading }] = useUpdateOrgMutation();
  const [orgName, setOrgName] = useState("");
  const [philosophy, setPhilosophy] = useState("");
  const [escalationLead, setEscalationLead] = useState("");

  const handleSave = async () => {
    if (!orgName.trim()) return;
    await updateOrg({ org_name: orgName.trim(), care_philosophy: philosophy.trim() || undefined, escalation_lead: escalationLead.trim() || undefined });
    onNext();
  };

  return (
    <div>
      <p style={{ margin: "0 0 1.5rem", color: "#6b7280", fontSize: "0.9rem", lineHeight: 1.5 }}>
        Start by naming your organization and setting the care philosophy your agents will use when drafting actions.
      </p>
      <div style={{ marginBottom: "1rem" }}>
        <label style={labelStyle}>Organization Name <span style={{ color: "#ef4444" }}>*</span></label>
        <input type="text" value={orgName} onChange={(e) => setOrgName(e.target.value)}
          placeholder="e.g. Sunrise Care Partners"
          style={inputStyle} />
      </div>
      <div style={{ marginBottom: "1rem" }}>
        <label style={labelStyle}>Care Philosophy</label>
        <textarea value={philosophy} onChange={(e) => setPhilosophy(e.target.value)}
          placeholder="Describe how your team approaches care — this shapes the tone of agent-drafted messages."
          rows={3} style={{ ...inputStyle, resize: "vertical" }} />
      </div>
      <div style={{ marginBottom: "1.5rem" }}>
        <label style={labelStyle}>Escalation Lead</label>
        <input type="text" value={escalationLead} onChange={(e) => setEscalationLead(e.target.value)}
          placeholder="e.g. Dr. Patricia Nguyen"
          style={inputStyle} />
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button onClick={handleSave} disabled={!orgName.trim() || isLoading} style={primaryBtn(!orgName.trim() || isLoading)}>
          {isLoading ? "Saving…" : "Save & Continue →"}
        </button>
      </div>
    </div>
  );
}

function StepCaregivers({ onNext }: { onNext: () => void }) {
  const { data: caregivers = [] } = useGetCaregiversQuery();

  return (
    <div>
      <p style={{ margin: "0 0 1.25rem", color: "#6b7280", fontSize: "0.9rem", lineHeight: 1.5 }}>
        Add the caregivers on your team. Each caregiver gets a per-day schedule — the scheduling agent uses availability when assigning transport and visit actions.
      </p>
      {caregivers.length > 0 && (
        <div style={{ marginBottom: "1rem" }}>
          {caregivers.map((c) => (
            <div key={c.caregiver_id} style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.6rem 0.75rem", borderRadius: 6, background: "#f0fdf4", border: "1px solid #bbf7d0", marginBottom: "0.4rem" }}>
              <span style={{ fontSize: "0.85rem", color: "#166534", fontWeight: 500 }}>✓</span>
              <span style={{ fontSize: "0.875rem", color: "#166534" }}>{c.name}</span>
            </div>
          ))}
        </div>
      )}
      <CaregiverForm onAdded={() => {}} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "1.5rem" }}>
        {caregivers.length === 0
          ? <p style={{ margin: 0, fontSize: "0.8rem", color: "#9ca3af" }}>Add at least one caregiver to continue.</p>
          : <p style={{ margin: 0, fontSize: "0.8rem", color: "#16a34a" }}>{caregivers.length} caregiver{caregivers.length > 1 ? "s" : ""} added.</p>
        }
        <button onClick={onNext} disabled={caregivers.length === 0} style={primaryBtn(caregivers.length === 0)}>
          Continue →
        </button>
      </div>
    </div>
  );
}

function StepPatients({ onNext }: { onNext: () => void }) {
  const [ingestFile, { isLoading }] = useIngestFileMutation();
  const { data: patients = [] } = useGetPatientsQuery();
  const [file, setFile] = useState<File | null>(null);
  const [done, setDone] = useState(false);

  const handleUpload = async () => {
    if (!file) return;
    await ingestFile({ file });
    setFile(null);
    setDone(true);
  };

  return (
    <div>
      <p style={{ margin: "0 0 1.25rem", color: "#6b7280", fontSize: "0.9rem", lineHeight: 1.5 }}>
        Upload a patient intake document — any text file describing the patient's name, conditions, medications, and preferences. The AI extracts the structured profile automatically.
      </p>
      <div style={{ background: "#fafafa", border: "1.5px dashed #d1d5db", borderRadius: 8, padding: "1.5rem", textAlign: "center", marginBottom: "1rem" }}>
        <p style={{ margin: "0 0 0.75rem", fontSize: "0.8rem", color: "#6b7280" }}>
          Try one of the sample files from <code style={{ background: "#f3f4f6", padding: "1px 4px", borderRadius: 3 }}>demo/uploads/intake/</code>
        </p>
        <input type="file" accept=".txt,.pdf,.png,.jpg,.jpeg"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          style={{ fontSize: "0.875rem" }} />
        {file && (
          <p style={{ margin: "0.5rem 0 0", fontSize: "0.8rem", color: "#3b82f6" }}>Selected: {file.name}</p>
        )}
      </div>
      {file && (
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "1rem" }}>
          <button onClick={handleUpload} disabled={isLoading} style={primaryBtn(isLoading)}>
            {isLoading ? "Processing…" : "Upload & Extract"}
          </button>
        </div>
      )}
      {patients.length > 0 && (
        <div style={{ marginBottom: "1rem" }}>
          {patients.map((p) => (
            <div key={p.patient_id} style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.6rem 0.75rem", borderRadius: 6, background: "#f0fdf4", border: "1px solid #bbf7d0", marginBottom: "0.4rem" }}>
              <span style={{ fontSize: "0.85rem", color: "#166534", fontWeight: 500 }}>✓</span>
              <span style={{ fontSize: "0.875rem", color: "#166534" }}>{p.name}</span>
            </div>
          ))}
        </div>
      )}
      {done && patients.length > 0 && (
        <p style={{ fontSize: "0.8rem", color: "#16a34a", margin: "0 0 0.75rem" }}>
          Patient added! Upload more, or continue when ready.
        </p>
      )}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "0.5rem" }}>
        {patients.length === 0
          ? <p style={{ margin: 0, fontSize: "0.8rem", color: "#9ca3af" }}>Upload at least one patient to continue.</p>
          : <p style={{ margin: 0, fontSize: "0.8rem", color: "#16a34a" }}>{patients.length} patient{patients.length > 1 ? "s" : ""} added.</p>
        }
        <button onClick={onNext} disabled={patients.length === 0} style={primaryBtn(patients.length === 0)}>
          Continue →
        </button>
      </div>
    </div>
  );
}

function StepReady({ onDone }: { onDone: () => void }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: "3rem", marginBottom: "0.75rem" }}>🎉</div>
      <h3 style={{ margin: "0 0 0.75rem", fontSize: "1.1rem", fontWeight: 600 }}>You're all set!</h3>
      <p style={{ margin: "0 0 1.5rem", color: "#6b7280", fontSize: "0.9rem", lineHeight: 1.6, maxWidth: 400, marginInline: "auto" }}>
        Your organization, caregivers, and patients are ready. Next, navigate to a patient and upload an update document to watch the agents generate their first action.
      </p>
      <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: "1rem 1.25rem", textAlign: "left", marginBottom: "1.5rem" }}>
        <p style={{ margin: "0 0 0.5rem", fontSize: "0.8rem", fontWeight: 600, color: "#374151" }}>Suggested next step</p>
        <ol style={{ margin: 0, paddingLeft: "1.25rem", fontSize: "0.85rem", color: "#6b7280", lineHeight: 1.7 }}>
          <li>Go to <strong>Patients</strong> → select a patient → open the <strong>Update</strong> tab</li>
          <li>Upload a file from <code style={{ background: "#f3f4f6", padding: "1px 4px", borderRadius: 3 }}>demo/uploads/updates/</code></li>
          <li>Review the proposed update and click <strong>Confirm</strong></li>
          <li>Watch the action appear in the <strong>Action Feed</strong></li>
        </ol>
      </div>
      <button onClick={onDone} style={{ ...primaryBtn(false), padding: "0.65rem 2rem", fontSize: "1rem" }}>
        Go to Dashboard →
      </button>
    </div>
  );
}

// ── Shared styles ─────────────────────────────────────────────────────────────

const labelStyle: React.CSSProperties = {
  display: "block", fontSize: "0.875rem", fontWeight: 500, marginBottom: "0.3rem", color: "#374151",
};

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "0.45rem 0.6rem", border: "1px solid #d1d5db", borderRadius: 6,
  fontSize: "0.875rem", fontFamily: "inherit", boxSizing: "border-box",
};

const primaryBtn = (disabled: boolean): React.CSSProperties => ({
  padding: "0.5rem 1.5rem", background: disabled ? "#d1d5db" : "#3b82f6", color: "#fff",
  border: "none", borderRadius: 6, cursor: disabled ? "not-allowed" : "pointer",
  fontSize: "0.875rem", fontWeight: 500,
});

// ── Main wizard ───────────────────────────────────────────────────────────────

export default function Onboarding() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);

  return (
    <div style={{ minHeight: "100vh", background: BG, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-start", padding: "3rem 1rem 4rem" }}>
      {/* Brand */}
      <div style={{ marginBottom: "2.5rem", textAlign: "center" }}>
        <div style={{ fontWeight: 600, fontSize: "1.4rem", letterSpacing: "0.06em", color: "#0a0a0a" }}>AgentCare</div>
        <div style={{ fontSize: "0.85rem", color: "#6b7280", marginTop: "0.2rem" }}>Multi-Agent Care Operations System</div>
      </div>

      {/* Step indicator */}
      <div style={{ display: "flex", alignItems: "center", marginBottom: "2.5rem", gap: 0 }}>
        {STEPS.map((s, i) => (
          <div key={s.n} style={{ display: "flex", alignItems: "center" }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.3rem" }}>
              <div style={{
                width: 32, height: 32, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                background: s.n < step ? "#16a34a" : s.n === step ? "#3b82f6" : "#e5e7eb",
                color: s.n <= step ? "#fff" : "#9ca3af", fontWeight: 600, fontSize: "0.85rem",
                transition: "background 0.2s",
              }}>
                {s.n < step ? "✓" : s.n}
              </div>
              <span style={{ fontSize: "0.72rem", color: s.n === step ? "#3b82f6" : s.n < step ? "#16a34a" : "#9ca3af", fontWeight: s.n === step ? 600 : 400 }}>
                {s.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div style={{ width: 60, height: 2, background: s.n < step ? "#16a34a" : "#e5e7eb", margin: "0 0.25rem 1.4rem", transition: "background 0.2s" }} />
            )}
          </div>
        ))}
      </div>

      {/* Card */}
      <div style={{ width: "100%", maxWidth: 560, background: "#fff", borderRadius: 12, boxShadow: CARD_SHADOW, padding: "2rem 2.25rem" }}>
        <h2 style={{ margin: "0 0 1.5rem", fontSize: "1.1rem", fontWeight: 700 }}>
          {step === 1 && "Set up your organization"}
          {step === 2 && "Add caregivers"}
          {step === 3 && "Add your first patient"}
          {step === 4 && "Setup complete"}
        </h2>

        {step === 1 && <StepOrg onNext={() => setStep(2)} />}
        {step === 2 && <StepCaregivers onNext={() => setStep(3)} />}
        {step === 3 && <StepPatients onNext={() => setStep(4)} />}
        {step === 4 && <StepReady onDone={() => navigate("/actions", { replace: true })} />}
      </div>
    </div>
  );
}
