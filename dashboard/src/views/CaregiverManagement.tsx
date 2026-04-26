import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { useLocation } from "react-router-dom";
import {
  useGetActionsQuery,
  useGetCaregiversQuery,
  useGetCaregiverScheduleQuery,
  useGetCaregiverAssignmentsQuery,
  useAssignSchedulingMutation,
  useConfirmSchedulingMutation,
  useDeclineSchedulingMutation,
  useCreateCaregiverMutation,
} from "../api/client";
import type { Action, Caregiver, DaySchedule } from "../types";
import ActionCard from "../components/ActionCard";

/** App shell / main content background (AppShell) */
const PAGE_BG = "#e8eaed";
const STRIP_CARD_HIGHLIGHT = "rgba(99, 102, 241, 0.14)";
const ROW_HOVER = "rgba(0, 0, 0, 0.04)";
const ROW_SELECTED = "rgba(59, 130, 246, 0.08)";

const SLOT_AVAILABLE = "#dcfce7";
const SLOT_BOOKED = "#dbeafe";
const SLOT_UNAVAILABLE = "#fee2e2";

// ── Scheduling task list ──────────────────────────────────────────────────────

function SchedulingStrip({
  selectedActionId,
  onSelect,
}: {
  selectedActionId: string | null;
  onSelect: (action: Action) => void;
}) {
  const { data: actions = [] } = useGetActionsQuery();

  const schedulingActions = actions.filter(
    (a) => a.scheduling_status === "pending_approval" || a.scheduling_status === "unconfirmed"
  );

  if (schedulingActions.length === 0) {
    return <p style={{ color: "#9ca3af", fontSize: "0.85rem", padding: "1rem" }}>No scheduling tasks pending.</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      {schedulingActions.map((action) => {
        const isSelected = action.action_id === selectedActionId;
        return (
          <button
            key={action.action_id}
            type="button"
            data-testid="scheduling-row"
            onClick={() => onSelect(action)}
            style={{
              display: "block",
              width: "100%",
              padding: "0.65rem 1rem",
              textAlign: "left",
              border: "none",
              borderBottom: "1px solid #d1d5db",
              borderLeft: isSelected ? "3px solid #6366f1" : "3px solid transparent",
              background: isSelected ? STRIP_CARD_HIGHLIGHT : "transparent",
              cursor: "pointer",
              fontSize: "0.875rem",
            }}
          >
            <div style={{ fontWeight: 500, color: "#111827", marginBottom: "0.2rem", lineHeight: 1.35 }}>
              {action.description}
            </div>
            <div style={{ display: "flex", gap: "0.4rem", alignItems: "center", flexWrap: "wrap" }}>
              {action.patient_name && (
                <span style={{ fontSize: "0.72rem", color: "#6b7280" }}>{action.patient_name}</span>
              )}
              <span
                style={{
                  fontSize: "0.65rem",
                  fontWeight: 600,
                  padding: "1px 7px",
                  borderRadius: "9999px",
                  background: action.scheduling_status === "unconfirmed"
                    ? "rgba(254, 240, 138, 0.6)"
                    : "rgba(219, 234, 254, 0.8)",
                  color: action.scheduling_status === "unconfirmed" ? "#854d0e" : "#1e40af",
                  border: action.scheduling_status === "unconfirmed"
                    ? "1px solid rgba(234, 179, 8, 0.35)"
                    : "1px solid rgba(147, 197, 253, 0.6)",
                }}
              >
                {action.scheduling_status === "unconfirmed" ? "Unconfirmed" : "Needs assignment"}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ── Scheduling detail panel ───────────────────────────────────────────────────

function SchedulingDetailPanel({
  action,
  caregivers,
}: {
  action: Action;
  caregivers: Caregiver[];
}) {
  const [assignScheduling, { isLoading: assigning }] = useAssignSchedulingMutation();
  const [confirmScheduling, { isLoading: confirming }] = useConfirmSchedulingMutation();
  const [declineScheduling, { isLoading: declining }] = useDeclineSchedulingMutation();
  const [pickedCaregiver, setPickedCaregiver] = useState("");

  const busy = assigning || confirming || declining;
  const assignedCaregiverName =
    caregivers.find((c) => c.caregiver_id === action.assigned_caregiver)?.name ??
    action.assigned_caregiver ?? "";

  return (
    <div style={{ padding: "1.5rem", overflowY: "auto", height: "100%", boxSizing: "border-box", background: PAGE_BG }}>
      <ActionCard action={action} />

      {action.scheduling_status === "pending_approval" && (
        <div
          style={{
            marginTop: "1rem",
            padding: "1rem 1.1rem",
            borderRadius: "14px",
            background: "#f5f6f8",
            border: "1px solid #d1d5db",
          }}
        >
          <div style={{ fontSize: "0.65rem", fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: "#4b5563", marginBottom: "0.65rem" }}>
            Assign Caregiver
          </div>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
            <select
              value={pickedCaregiver}
              onChange={(e) => setPickedCaregiver(e.target.value)}
              disabled={busy}
              style={{
                flex: 1,
                minWidth: "160px",
                border: "1px solid #d1d5db",
                borderRadius: "8px",
                padding: "0.4rem 0.6rem",
                fontSize: "0.85rem",
                background: "#fff",
                color: "#111827",
                cursor: busy ? "not-allowed" : "pointer",
              }}
            >
              <option value="">Select caregiver…</option>
              {caregivers.map((c) => (
                <option key={c.caregiver_id} value={c.caregiver_id}>
                  {c.name}{c.availability_today ? "" : " (unavailable today)"}
                </option>
              ))}
            </select>
            <button
              type="button"
              data-testid="assign-btn"
              disabled={!pickedCaregiver || busy}
              onClick={() => {
                assignScheduling({ actionId: action.action_id, caregiver_id: pickedCaregiver });
                setPickedCaregiver("");
              }}
              style={{
                padding: "0.42rem 1.1rem",
                borderRadius: "9999px",
                border: "1px solid rgba(147, 197, 253, 0.95)",
                background: !pickedCaregiver || busy ? "rgba(209, 213, 219, 0.8)" : "rgba(191, 219, 254, 0.75)",
                color: !pickedCaregiver || busy ? "#6b7280" : "#0a0a0a",
                cursor: !pickedCaregiver || busy ? "not-allowed" : "pointer",
                fontSize: "0.8rem",
                fontWeight: 600,
              }}
            >
              {assigning ? "Assigning…" : "Assign"}
            </button>
          </div>
        </div>
      )}

      {action.scheduling_status === "unconfirmed" && (
        <div
          style={{
            marginTop: "1rem",
            padding: "1rem 1.1rem",
            borderRadius: "14px",
            background: "#f5f6f8",
            border: "1px solid #d1d5db",
          }}
        >
          <div style={{ fontSize: "0.65rem", fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: "#4b5563", marginBottom: "0.5rem" }}>
            Awaiting Confirmation
          </div>
          {assignedCaregiverName && (
            <p style={{ margin: "0 0 0.65rem", fontSize: "0.85rem", color: "#374151" }}>
              Assigned to <strong>{assignedCaregiverName}</strong>
            </p>
          )}
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              type="button"
              data-testid="confirm-btn"
              disabled={busy}
              onClick={() => confirmScheduling(action.action_id)}
              style={{
                padding: "0.42rem 1.1rem",
                borderRadius: "9999px",
                border: "1px solid rgba(52, 211, 153, 0.6)",
                background: busy ? "rgba(209, 213, 219, 0.8)" : "rgba(167, 243, 208, 0.65)",
                color: busy ? "#6b7280" : "#065f46",
                cursor: busy ? "not-allowed" : "pointer",
                fontSize: "0.8rem",
                fontWeight: 600,
              }}
            >
              {confirming ? "Confirming…" : "Confirm"}
            </button>
            <button
              type="button"
              data-testid="decline-btn"
              disabled={busy}
              onClick={() => declineScheduling(action.action_id)}
              style={{
                padding: "0.42rem 1.1rem",
                borderRadius: "9999px",
                border: "1px solid rgba(248, 113, 113, 0.5)",
                background: busy ? "rgba(209, 213, 219, 0.8)" : "rgba(254, 202, 202, 0.55)",
                color: busy ? "#6b7280" : "#991b1b",
                cursor: busy ? "not-allowed" : "pointer",
                fontSize: "0.8rem",
                fontWeight: 600,
              }}
            >
              {declining ? "Declining…" : "Decline"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── 14-day schedule grid (task 5.3) ───────────────────────────────────────────

function scheduleSlotColor(status: "available" | "booked" | "unavailable"): string {
  if (status === "booked") return SLOT_BOOKED;
  if (status === "unavailable") return SLOT_UNAVAILABLE;
  return SLOT_AVAILABLE;
}

function ScheduleLegend() {
  const items: { label: string; color: string }[] = [
    { label: "Available", color: SLOT_AVAILABLE },
    { label: "Booked", color: SLOT_BOOKED },
    { label: "Unavailable", color: SLOT_UNAVAILABLE },
  ];
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "0.75rem",
        marginBottom: "0.75rem",
        fontSize: "0.7rem",
        color: "#6b7280",
      }}
    >
      {items.map(({ label, color }) => (
        <span key={label} style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: 2,
              background: color,
              border: "1px solid rgba(0,0,0,0.06)",
              flexShrink: 0,
            }}
            aria-hidden
          />
          {label}
        </span>
      ))}
    </div>
  );
}

function ScheduleGrid({ caregiverId }: { caregiverId: string }) {
  const { data: slots = [], isLoading } = useGetCaregiverScheduleQuery(caregiverId);

  if (isLoading) {
    return (
      <div style={{ minHeight: "5rem", display: "flex", alignItems: "center" }}>
        <p style={{ margin: 0, fontSize: "0.85rem", color: "#6b7280" }}>Loading schedule…</p>
      </div>
    );
  }
  if (slots.length === 0) {
    return (
      <div style={{ minHeight: "3rem" }}>
        <p style={{ margin: 0, fontSize: "0.85rem", color: "#9ca3af" }}>No schedule data.</p>
      </div>
    );
  }

  return (
    <div>
      <ScheduleLegend />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
          gap: "6px",
          maxWidth: "100%",
        }}
      >
        {slots.map((slot, i) => (
          <div
            key={i}
            title={`${slot.date} ${slot.shift}`}
            style={{
              minHeight: "2.6rem",
              padding: "6px 4px",
              backgroundColor: scheduleSlotColor(slot.status),
              borderRadius: "6px",
              fontSize: "0.7rem",
              textAlign: "center",
              color: "#374151",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
              boxSizing: "border-box" as const,
            }}
          >
            <div style={{ fontWeight: 600, lineHeight: 1.2 }}>{slot.date.slice(5)}</div>
            <div style={{ color: "#4b5563", fontSize: "0.65rem", lineHeight: 1.2, marginTop: 2 }}>{slot.shift}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Assignment list (task 5.4) ────────────────────────────────────────────────

function AssignmentList({ caregiverId }: { caregiverId: string }) {
  const { data: assignments = [], isLoading } = useGetCaregiverAssignmentsQuery(caregiverId);
  if (isLoading) {
    return (
      <div style={{ minHeight: "4rem", display: "flex", alignItems: "center" }}>
        <p style={{ margin: 0, fontSize: "0.85rem", color: "#6b7280" }}>Loading assignments…</p>
      </div>
    );
  }
  if (assignments.length === 0) {
    return (
      <div>
        <p style={{ margin: 0, fontSize: "0.875rem", color: "#6b7280" }}>No assignments yet</p>
        <p style={{ margin: "0.4rem 0 0", fontSize: "0.8rem", color: "#9ca3af", lineHeight: 1.45, maxWidth: "28rem" }}>
          Proposed visit times and tasks assigned to this caregiver will show up here.
        </p>
      </div>
    );
  }
  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: "0.875rem" }}>
      {assignments.map((a, idx) => (
        <li
          key={a.option_id}
          style={{
            padding: "0.55rem 0",
            borderBottom: idx < assignments.length - 1 ? "1px solid rgba(0,0,0,0.06)" : "none",
            color: "#374151",
          }}
        >
          {a.proposed_date} {a.proposed_time} — {a.caregiver_name}
        </li>
      ))}
    </ul>
  );
}

// ── Caregiver detail panel ────────────────────────────────────────────────────

const detailSectionStyle: CSSProperties = {
  background: "rgba(255, 255, 255, 0.5)",
  border: "1px solid rgba(0, 0, 0, 0.08)",
  borderRadius: "8px",
  padding: "1rem 1.1rem",
};

const sectionHeadingStyle: CSSProperties = {
  margin: "0 0 0.75rem",
  fontSize: "0.8rem",
  fontWeight: 600,
  color: "#374151",
};

function CaregiverDetailPanel({ caregiver }: { caregiver: Caregiver }) {
  return (
    <div
      style={{
        boxSizing: "border-box",
        padding: "1.25rem 1.5rem 2rem",
        overflowY: "auto",
        height: "100%",
        background: PAGE_BG,
      }}
    >
      <div style={{ width: "100%" }}>
        <header
          style={{
            marginBottom: "1.25rem",
            paddingBottom: "1rem",
            borderBottom: "1px solid rgba(0, 0, 0, 0.08)",
          }}
        >
          <h2
            style={{
              margin: "0 0 0.5rem",
              fontSize: "1.2rem",
              fontWeight: 700,
              color: "#111827",
              letterSpacing: "-0.02em",
            }}
          >
            {caregiver.name}
          </h2>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", alignItems: "center" }}>
            <span
              style={{
                display: "inline-block",
                fontSize: "0.75rem",
                fontWeight: 500,
                padding: "0.2rem 0.55rem",
                borderRadius: "9999px",
                background: caregiver.availability_today ? "rgba(16, 185, 129, 0.15)" : "rgba(107, 114, 128, 0.1)",
                color: caregiver.availability_today ? "#047857" : "#4b5563",
              }}
            >
              {caregiver.availability_today ? "Available today" : "Not available today"}
            </span>
            {caregiver.booked_today ? (
              <span
                style={{
                  display: "inline-block",
                  fontSize: "0.75rem",
                  fontWeight: 500,
                  padding: "0.2rem 0.55rem",
                  borderRadius: "9999px",
                  background: "rgba(59, 130, 246, 0.12)",
                  color: "#1d4ed8",
                }}
              >
                Booked
              </span>
            ) : null}
          </div>
        </header>

        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          <section style={detailSectionStyle}>
            <h3 style={sectionHeadingStyle}>14-day schedule</h3>
            <ScheduleGrid caregiverId={caregiver.caregiver_id} />
          </section>
          <section style={detailSectionStyle}>
            <h3 style={sectionHeadingStyle}>Assignments</h3>
            <AssignmentList caregiverId={caregiver.caregiver_id} />
          </section>
        </div>
      </div>
    </div>
  );
}

// ── Main view (task 5.1) — resizable split between scheduling & caregivers ───

const MIN_SCHED_PX = 80;
const MIN_CARE_PX = 100;
const SPLITTER_H = 10;

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;
type Day = typeof DAYS[number];

function AddCaregiverModal({ onClose }: { onClose: () => void }) {
  const [createCaregiver, { isLoading }] = useCreateCaregiverMutation();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState<"caregiver" | "admin">("caregiver");
  const [schedule, setSchedule] = useState<Partial<Record<Day, DaySchedule>>>({});

  const toggleDay = (day: Day) => {
    setSchedule((prev) => {
      const next = { ...prev };
      if (next[day]) delete next[day];
      else next[day] = { start: "09:00", end: "17:00" };
      return next;
    });
  };

  const setHour = (day: Day, field: "start" | "end", val: string) => {
    setSchedule((prev) => ({ ...prev, [day]: { ...prev[day]!, [field]: val } }));
  };

  const handleSubmit = async () => {
    if (!name.trim() || !email.trim()) return;
    await createCaregiver({ name: name.trim(), email: email.trim(), phone: phone.trim(), role, schedule });
    onClose();
  };

  const canSubmit = name.trim() && email.trim() && !isLoading;

  return (
    <>
      <div onClick={onClose} style={{ position: "fixed", inset: 0, backgroundColor: "rgba(0,0,0,0.4)", zIndex: 60 }} />
      <div style={{
        position: "fixed", top: "50%", left: "50%", transform: "translate(-50%,-50%)",
        width: "520px", maxWidth: "95vw", backgroundColor: "#fff", borderRadius: "8px",
        boxShadow: "0 20px 60px rgba(0,0,0,0.2)", zIndex: 70, display: "flex", flexDirection: "column",
        maxHeight: "90vh", overflow: "hidden",
      }}>
        <div style={{ padding: "1.25rem 1.5rem", borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
          <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>Add Caregiver</h2>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1.25rem", color: "#6b7280" }}>×</button>
        </div>

        <div style={{ padding: "1.25rem 1.5rem", overflowY: "auto" }}>
          {(["Name", "Email", "Phone"] as const).map((label) => {
            const key = label.toLowerCase() as "name" | "email" | "phone";
            const val = key === "name" ? name : key === "email" ? email : phone;
            const setter = key === "name" ? setName : key === "email" ? setEmail : setPhone;
            return (
              <div key={label} style={{ marginBottom: "0.875rem" }}>
                <label style={{ display: "block", fontSize: "0.875rem", fontWeight: 500, marginBottom: "0.25rem" }}>{label}</label>
                <input type="text" value={val} onChange={(e) => setter(e.target.value)}
                  style={{ width: "100%", padding: "0.4rem 0.5rem", border: "1px solid #d1d5db", borderRadius: "6px", fontSize: "0.875rem", boxSizing: "border-box" }} />
              </div>
            );
          })}

          <div style={{ marginBottom: "1rem" }}>
            <label style={{ display: "block", fontSize: "0.875rem", fontWeight: 500, marginBottom: "0.25rem" }}>Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value as "caregiver" | "admin")}
              style={{ width: "100%", padding: "0.4rem 0.5rem", border: "1px solid #d1d5db", borderRadius: "6px", fontSize: "0.875rem" }}>
              <option value="caregiver">Caregiver</option>
              <option value="admin">Admin</option>
            </select>
          </div>

          <div>
            <p style={{ fontSize: "0.875rem", fontWeight: 500, marginBottom: "0.5rem" }}>Weekly Schedule</p>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
              <thead>
                <tr style={{ color: "#6b7280" }}>
                  <th style={{ width: "40px", textAlign: "left", paddingBottom: "0.25rem" }}></th>
                  <th style={{ width: "60px", textAlign: "left", paddingBottom: "0.25rem" }}>Day</th>
                  <th style={{ textAlign: "left", paddingBottom: "0.25rem" }}>Start</th>
                  <th style={{ textAlign: "left", paddingBottom: "0.25rem" }}>End</th>
                </tr>
              </thead>
              <tbody>
                {DAYS.map((day) => {
                  const entry = schedule[day];
                  return (
                    <tr key={day} style={{ borderTop: "1px solid #f3f4f6" }}>
                      <td style={{ padding: "0.35rem 0" }}>
                        <input type="checkbox" checked={!!entry} onChange={() => toggleDay(day)} />
                      </td>
                      <td style={{ padding: "0.35rem 0", color: entry ? "#111827" : "#9ca3af" }}>{day}</td>
                      <td style={{ padding: "0.35rem 0.5rem 0.35rem 0" }}>
                        <input type="text" disabled={!entry} value={entry?.start ?? ""}
                          onChange={(e) => setHour(day, "start", e.target.value)} placeholder="09:00"
                          style={{ width: "70px", padding: "0.25rem 0.375rem", border: "1px solid #d1d5db", borderRadius: "4px", fontSize: "0.8rem", opacity: entry ? 1 : 0.4 }} />
                      </td>
                      <td style={{ padding: "0.35rem 0" }}>
                        <input type="text" disabled={!entry} value={entry?.end ?? ""}
                          onChange={(e) => setHour(day, "end", e.target.value)} placeholder="17:00"
                          style={{ width: "70px", padding: "0.25rem 0.375rem", border: "1px solid #d1d5db", borderRadius: "4px", fontSize: "0.8rem", opacity: entry ? 1 : 0.4 }} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div style={{ padding: "1rem 1.5rem", borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: "0.75rem", flexShrink: 0 }}>
          <button onClick={onClose} style={{ padding: "0.5rem 1rem", border: "1px solid #d1d5db", borderRadius: "6px", background: "#fff", cursor: "pointer", fontSize: "0.875rem" }}>Cancel</button>
          <button onClick={handleSubmit} disabled={!canSubmit}
            style={{ padding: "0.5rem 1.25rem", backgroundColor: canSubmit ? "#3b82f6" : "#d1d5db", color: "#fff", border: "none", borderRadius: "6px", cursor: canSubmit ? "pointer" : "not-allowed", fontSize: "0.875rem", fontWeight: 500 }}>
            {isLoading ? "Adding…" : "Add Caregiver"}
          </button>
        </div>
      </div>
    </>
  );
}

export default function CaregiverManagement() {
  const location = useLocation();
  const highlightActionId: string | undefined = (location.state as any)?.highlightActionId;

  const { data: caregivers = [], isLoading } = useGetCaregiversQuery();
  const { data: actions = [] } = useGetActionsQuery();
  const [selectedActionId, setSelectedActionId] = useState<string | null>(highlightActionId ?? null);
  const [selectedCaregiver, setSelectedCaregiver] = useState<Caregiver | null>(null);
  const [showAddCaregiver, setShowAddCaregiver] = useState(false);

  // Auto-select when deep-linked from ActionCard "View Scheduling"
  useEffect(() => {
    if (highlightActionId) {
      setSelectedActionId(highlightActionId);
      setSelectedCaregiver(null);
    }
  }, [highlightActionId]);

  // Derive from live RTK cache so it updates reactively after assign/confirm mutations
  const selectedAction = selectedActionId
    ? (actions.find((a) => a.action_id === selectedActionId) ?? null)
    : null;

  const splitRef = useRef<HTMLDivElement>(null);
  const schedHeaderRef = useRef<HTMLDivElement>(null);
  const careHeaderRef = useRef<HTMLDivElement>(null);
  const [schedContentHeight, setSchedContentHeight] = useState(300);
  useLayoutEffect(() => {
    const el = splitRef.current;
    if (!el) return;
    const h = el.getBoundingClientRect().height;
    if (h < 40) return;
    const shH = schedHeaderRef.current?.offsetHeight ?? 48;
    const chH = careHeaderRef.current?.offsetHeight ?? 44;
    const maxSched = h - shH - SPLITTER_H - chH - MIN_CARE_PX;
    if (maxSched < MIN_SCHED_PX) return;
    const targetContent = Math.max(MIN_SCHED_PX, Math.min(maxSched, Math.floor(maxSched * 0.58)));
    setSchedContentHeight(targetContent);
  }, []);

  const onSplitPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    const container = splitRef.current;
    if (!container) return;
    const handleEl = e.currentTarget;
    handleEl.setPointerCapture(e.pointerId);
    const startY = e.clientY;
    const startH = schedContentHeight;
    const capId = e.pointerId;

    const onMove = (pe: PointerEvent) => {
      if (pe.pointerId !== capId) return;
      const shH = schedHeaderRef.current?.offsetHeight ?? 0;
      const chH = careHeaderRef.current?.offsetHeight ?? 0;
      const rect = container.getBoundingClientRect();
      const maxSched = Math.max(MIN_SCHED_PX, rect.height - shH - SPLITTER_H - chH - MIN_CARE_PX);
      const next = Math.round(startH + (pe.clientY - startY));
      setSchedContentHeight(Math.max(MIN_SCHED_PX, Math.min(maxSched, next)));
    };

    const onUp = (pe: PointerEvent) => {
      if (pe.pointerId !== capId) return;
      try {
        handleEl.releasePointerCapture(capId);
      } catch {
        /* ignore if already released */
      }
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
      document.removeEventListener("pointercancel", onUp);
      document.body.style.cursor = "";
      document.body.style.removeProperty("user-select");
    };

    document.addEventListener("pointermove", onMove, { passive: false });
    document.addEventListener("pointerup", onUp);
    document.addEventListener("pointercancel", onUp);
    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
  };

  return (
    <div style={{ display: "flex", height: "calc(100vh - 56px)" }}>
      {/* Left: scheduling (fixed top height) + splitter + caregivers (flex) */}
      <div
        style={{
          width: "340px",
          borderRight: "1px solid #e5e7eb",
          display: "flex",
          flexDirection: "column",
          flexShrink: 0,
          background: PAGE_BG,
          minHeight: 0,
        }}
      >
        <div
          ref={splitRef}
          style={{
            flex: 1,
            minHeight: 0,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <div
            ref={schedHeaderRef}
            style={{ padding: "1rem", borderBottom: "1px solid #d1d5db", background: PAGE_BG, flexShrink: 0 }}
          >
            <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>Pending Tasks</span>
          </div>
          <div
            style={{
              height: schedContentHeight,
              minHeight: MIN_SCHED_PX,
              overflow: "auto",
              flexShrink: 0,
              background: PAGE_BG,
            }}
          >
            <SchedulingStrip
              selectedActionId={selectedActionId}
              onSelect={(action) => {
                setSelectedActionId(action.action_id);
                setSelectedCaregiver(null);
              }}
            />
          </div>

          <div
            role="separator"
            aria-orientation="horizontal"
            aria-label="Drag to resize pending tasks and caregiver sections"
            onPointerDown={onSplitPointerDown}
            style={{
              height: SPLITTER_H,
              minHeight: SPLITTER_H,
              flexShrink: 0,
              cursor: "row-resize",
              touchAction: "none" as const,
              background: "rgba(0, 0, 0, 0.04)",
              borderTop: "1px solid rgba(0, 0, 0, 0.07)",
              borderBottom: "1px solid rgba(0, 0, 0, 0.07)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 2,
            }}
            title="Drag to resize"
          >
            <span
              style={{
                width: "40px",
                height: "4px",
                borderRadius: "2px",
                background: "#64748b",
                boxShadow: "0 1px 0 rgba(255,255,255,0.5)",
                pointerEvents: "none" as const,
              }}
            />
          </div>

          <div
            style={{
              flex: 1,
              minHeight: MIN_CARE_PX,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            <div
              ref={careHeaderRef}
              style={{
                padding: "0.75rem 1rem",
                borderBottom: "1px solid #d1d5db",
                fontWeight: 500,
                fontSize: "0.875rem",
                background: PAGE_BG,
                flexShrink: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              Caregivers
              <button
                onClick={() => setShowAddCaregiver(true)}
                style={{ fontSize: "0.75rem", fontWeight: 500, color: "#2563eb", background: "none", border: "1px solid #2563eb", borderRadius: 4, padding: "2px 8px", cursor: "pointer" }}
              >
                + Add
              </button>
            </div>
            {showAddCaregiver && <AddCaregiverModal onClose={() => setShowAddCaregiver(false)} />}
            <div style={{ flex: 1, minHeight: 0, overflow: "auto", background: PAGE_BG }}>
              {isLoading && <p style={{ padding: "0.75rem", fontSize: "0.85rem", color: "#6b7280" }}>Loading…</p>}
              {caregivers.map((c) => (
                <button
                  key={c.caregiver_id}
                  onClick={() => { setSelectedCaregiver(c); setSelectedActionId(null); }}
                  type="button"
                  style={{
                    display: "block",
                    width: "100%",
                    padding: "0.5rem 1rem",
                    textAlign: "left",
                    border: "none",
                    borderBottom: "1px solid #d1d5db",
                    background:
                      selectedCaregiver?.caregiver_id === c.caregiver_id ? ROW_SELECTED : "transparent",
                    cursor: "pointer",
                    fontSize: "0.875rem",
                  }}
                  onMouseEnter={(ev) => {
                    if (selectedCaregiver?.caregiver_id !== c.caregiver_id) {
                      (ev.currentTarget as HTMLButtonElement).style.background = ROW_HOVER;
                    }
                  }}
                  onMouseLeave={(ev) => {
                    (ev.currentTarget as HTMLButtonElement).style.background =
                      selectedCaregiver?.caregiver_id === c.caregiver_id ? ROW_SELECTED : "transparent";
                  }}
                >
                  {c.name}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Right: scheduling detail or caregiver detail */}
      <div style={{ flex: 1, overflow: "hidden", minHeight: 0, background: PAGE_BG }}>
        {selectedAction ? (
          <SchedulingDetailPanel action={selectedAction} caregivers={caregivers} />
        ) : selectedCaregiver ? (
          <CaregiverDetailPanel caregiver={selectedCaregiver} />
        ) : (
          <div
            style={{
              boxSizing: "border-box",
              padding: "2rem 1.5rem",
              color: "#9ca3af",
              background: PAGE_BG,
              height: "100%",
            }}
          >
            <div style={{ width: "100%", fontSize: "0.9rem" }}>
              Select a pending task or caregiver to view details.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
