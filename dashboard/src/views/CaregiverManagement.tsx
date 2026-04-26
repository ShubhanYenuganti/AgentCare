import { useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { formatTimeRangeLocal } from "../utils/formatActionDate";
import { useLocation, useNavigate } from "react-router-dom";
import {
  useGetActionsQuery,
  useGetCaregiversQuery,
  useGetCaregiverScheduleQuery,
  useGetCaregiverAssignmentsQuery,
  useGetCaregiversAvailableQuery,
  useAssignCaregiverToActionMutation,
  useCreateCaregiverMutation,
} from "../api/client";
import type { Action, Caregiver, CaregiverAssignment, CaregiverScheduleSlot, DaySchedule } from "../types";

type ParsedActionSchedule = { start_time?: string; end_time?: string };

function parseActionSchedule(raw: string | null | undefined): ParsedActionSchedule | null {
  if (raw == null || raw === "") return null;
  try {
    const j = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (j && typeof j === "object") {
      const st = (j as { start_time?: string; start?: string }).start_time ?? (j as { start?: string }).start;
      const en = (j as { end_time?: string; end?: string }).end_time ?? (j as { end?: string }).end;
      if (st || en) return { start_time: st, end_time: en };
    }
  } catch {
    return null;
  }
  return null;
}

function calendarDateFromIso(iso: string): string | null {
  const m = iso.trim().match(/^(\d{4}-\d{2}-\d{2})/);
  return m ? m[1]! : null;
}

type BookingRow = {
  action_id: string;
  description: string;
  patient_name: string;
  start?: string;
  end?: string;
};

function indexBookingsByDate(assignments: CaregiverAssignment[]): Map<string, BookingRow[]> {
  const map = new Map<string, BookingRow[]>();
  for (const a of assignments) {
    const p = parseActionSchedule(a.schedule);
    if (!p?.start_time) continue;
    const d = calendarDateFromIso(p.start_time);
    if (!d) continue;
    const row: BookingRow = {
      action_id: a.action_id,
      description: a.description,
      patient_name: a.patient_name,
      start: p.start_time,
      end: p.end_time,
    };
    const list = map.get(d) ?? [];
    list.push(row);
    map.set(d, list);
  }
  return map;
}
import { formatReviewByLocal } from "../utils/formatActionDate";
import { urgencyDisplayLabel } from "../utils/urgencyLabels";

const PAGE_BG = "#e8eaed";
const ROW_HOVER = "rgba(0, 0, 0, 0.04)";
const ROW_SELECTED = "rgba(59, 130, 246, 0.08)";

const SLOT_AVAILABLE = "#dcfce7";
const SLOT_BOOKED = "#dbeafe";
const SLOT_UNAVAILABLE = "#fee2e2";

// ── Assignment panel ──────────────────────────────────────────────────────────

function CaregiverAssignRow({
  caregiver,
  onAssign,
  assigning,
}: {
  caregiver: { caregiver_id: string; name: string };
  onAssign: (id: string) => void;
  assigning: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0.55rem 0.75rem",
        borderBottom: "1px solid #e5e7eb",
        fontSize: "0.875rem",
      }}
    >
      <span style={{ color: "#111827", fontWeight: 500 }}>{caregiver.name}</span>
      <button
        type="button"
        disabled={assigning}
        onClick={() => onAssign(caregiver.caregiver_id)}
        style={{
          padding: "0.3rem 0.85rem",
          borderRadius: "9999px",
          border: "1px solid rgba(147, 197, 253, 0.95)",
          background: assigning ? "rgba(209,213,219,0.8)" : "rgba(191,219,254,0.75)",
          color: assigning ? "#6b7280" : "#0a0a0a",
          cursor: assigning ? "not-allowed" : "pointer",
          fontSize: "0.78rem",
          fontWeight: 600,
        }}
      >
        Assign
      </button>
    </div>
  );
}

function AssignmentPanel({ action, onClose }: { action: Action; onClose: () => void }) {
  const navigate = useNavigate();
  const [assignCaregiver, { isLoading: assigning }] = useAssignCaregiverToActionMutation();

  const hasSchedule = Boolean(action.schedule?.start_time && action.schedule?.end_time);
  const { data: available = [], isLoading } = useGetCaregiversAvailableQuery(
    hasSchedule
      ? { start_time: action.schedule!.start_time, end_time: action.schedule!.end_time }
      : undefined
  );

  const handleAssign = async (caregiverId: string) => {
    await assignCaregiver({ actionId: action.action_id, assigned_caregiver: caregiverId });
    navigate("/");
  };

  return (
    <div
      style={{
        boxSizing: "border-box",
        padding: "1.5rem",
        overflowY: "auto",
        height: "100%",
        background: PAGE_BG,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "1rem" }}>
        <div>
          <div style={{ fontSize: "0.65rem", fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: "#4b5563", marginBottom: "0.3rem" }}>
            Schedule Task
          </div>
          <p style={{ margin: 0, fontSize: "1rem", fontWeight: 600, color: "#111827", lineHeight: 1.4 }}>
            {action.description}
          </p>
          {action.patient_name && (
            <p style={{ margin: "0.25rem 0 0", fontSize: "0.8rem", color: "#6b7280" }}>
              {action.patient_name}
            </p>
          )}
          {hasSchedule && (
            <p style={{ margin: "0.35rem 0 0", fontSize: "0.78rem", color: "#374151" }}>
              <span style={{ color: "#6b7280" }}>Window: </span>
              {action.schedule!.start_time} – {action.schedule!.end_time}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1.25rem", color: "#6b7280", lineHeight: 1, padding: "0 0.25rem" }}
        >
          ×
        </button>
      </div>

      <div
        style={{
          marginTop: "0.5rem",
          borderRadius: "14px",
          background: "#f5f6f8",
          border: "1px solid #d1d5db",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "0.6rem 0.75rem",
            borderBottom: "1px solid #e5e7eb",
            fontSize: "0.65rem",
            fontWeight: 600,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "#4b5563",
          }}
        >
          {hasSchedule ? "Available Caregivers" : "Caregivers by Workload"}
        </div>

        {isLoading && (
          <p style={{ margin: 0, padding: "1rem", fontSize: "0.85rem", color: "#6b7280" }}>Loading…</p>
        )}

        {!isLoading && available.length === 0 && hasSchedule && (
          <p style={{ margin: 0, padding: "1rem", fontSize: "0.85rem", color: "#9ca3af" }}>
            No caregivers available in that window. All caregivers shown below.
          </p>
        )}

        {!isLoading &&
          available.map((c) => (
            <CaregiverAssignRow key={c.caregiver_id} caregiver={c} onAssign={handleAssign} assigning={assigning} />
          ))}
      </div>
    </div>
  );
}

// ── 14-day schedule grid ──────────────────────────────────────────────────────

function scheduleSlotColor(status: "available" | "booked" | "unavailable"): string {
  if (status === "booked") return SLOT_BOOKED;
  if (status === "unavailable") return SLOT_UNAVAILABLE;
  return SLOT_AVAILABLE;
}

/** API returns `caregiver_schedule` rows with `available` / `booked`, not `status`. */
function deriveSlotStatus(slot: CaregiverScheduleSlot): "available" | "booked" | "unavailable" {
  const explicit = slot.status;
  if (explicit === "booked" || explicit === "unavailable" || explicit === "available") {
    return explicit;
  }
  if (Number(slot.booked) === 1) return "booked";
  if (Number(slot.available) === 0) return "unavailable";
  return "available";
}

function stripHms(t: string): string {
  const m = t.trim().match(/^(\d{1,2}:\d{2})(?::\d{2})?/);
  return m ? m[1]! : t.trim();
}

/** Prefer explicit `shift`; else format DB `start_time` / `end_time` (e.g. seed `08:00`–`16:00`), or "Off" when not working. */
function formatSlotShiftLabel(slot: CaregiverScheduleSlot): string {
  if (slot.shift) return slot.shift;
  const s = slot.start_time?.trim();
  const e = slot.end_time?.trim();
  if (s && e) return `${stripHms(s)}–${stripHms(e)}`;
  if (!s && !e) return "Off";
  return stripHms(s || e || "—");
}

function ScheduleLegend() {
  const items: { label: string; color: string }[] = [
    { label: "Available", color: SLOT_AVAILABLE },
    { label: "Booked", color: SLOT_BOOKED },
    { label: "Unavailable", color: SLOT_UNAVAILABLE },
  ];
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", marginBottom: "0.75rem", fontSize: "0.7rem", color: "#6b7280" }}>
      {items.map(({ label, color }) => (
        <span key={label} style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: color, border: "1px solid rgba(0,0,0,0.06)", flexShrink: 0 }} aria-hidden />
          {label}
        </span>
      ))}
    </div>
  );
}

function ScheduleGrid({ caregiverId }: { caregiverId: string }) {
  const { data: slots = [], isLoading } = useGetCaregiverScheduleQuery(caregiverId);
  const { data: assignments = [] } = useGetCaregiverAssignmentsQuery(caregiverId);
  const [openBookedDate, setOpenBookedDate] = useState<string | null>(null);
  const bookingsByDate = indexBookingsByDate(assignments);

  if (isLoading) return <p style={{ margin: 0, fontSize: "0.85rem", color: "#6b7280" }}>Loading schedule…</p>;
  if (slots.length === 0) return <p style={{ margin: 0, fontSize: "0.85rem", color: "#9ca3af" }}>No schedule data.</p>;

  const openSlot = openBookedDate ? slots.find((s) => s.date === openBookedDate) : undefined;
  const openStatus = openSlot ? deriveSlotStatus(openSlot) : null;
  const openBookings = openBookedDate ? bookingsByDate.get(openBookedDate) ?? [] : [];
  const openShift = openSlot ? formatSlotShiftLabel(openSlot) : "";

  return (
    <div>
      <ScheduleLegend />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, minmax(0, 1fr))", gap: "6px", maxWidth: "100%" }}>
        {slots.map((slot) => {
          const st = deriveSlotStatus(slot);
          const shift = formatSlotShiftLabel(slot);
          const isBooked = st === "booked";
          const isOpen = isBooked && openBookedDate === slot.date;
          return (
            <div
              key={slot.date}
              role={isBooked ? "button" : undefined}
              tabIndex={isBooked ? 0 : undefined}
              onClick={() => {
                if (!isBooked) {
                  return;
                }
                setOpenBookedDate((d) => (d === slot.date ? null : slot.date));
              }}
              onKeyDown={(e) => {
                if (!isBooked) return;
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setOpenBookedDate((d) => (d === slot.date ? null : slot.date));
                }
              }}
              title={
                isBooked
                  ? `${slot.date} · Booked · ${shift} — click for visit time`
                  : `${slot.date} · ${st} · ${shift}`
              }
              style={{
                minHeight: "2.6rem",
                padding: "6px 4px",
                backgroundColor: scheduleSlotColor(st),
                borderRadius: "6px",
                fontSize: "0.7rem",
                textAlign: "center",
                color: "#374151",
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                alignItems: "center",
                boxSizing: "border-box" as const,
                cursor: isBooked ? "pointer" : "default",
                outline: isOpen ? "2px solid #2563eb" : "none",
                outlineOffset: 1,
              }}
            >
              <div style={{ fontWeight: 600, lineHeight: 1.2 }}>{slot.date.slice(5)}</div>
              <div style={{ color: "#4b5563", fontSize: "0.65rem", lineHeight: 1.2, marginTop: 2 }}>{shift}</div>
            </div>
          );
        })}
      </div>
      {openBookedDate && openStatus === "booked" && openSlot && (
        <div
          style={{
            marginTop: "0.75rem",
            padding: "0.65rem 0.75rem",
            borderRadius: "8px",
            background: "rgba(219, 234, 254, 0.65)",
            border: "1px solid rgba(59, 130, 246, 0.35)",
            fontSize: "0.8rem",
            color: "#1e3a8a",
          }}
        >
          <div style={{ fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" as const, marginBottom: "0.4rem" }}>
            Booking · {openBookedDate}
          </div>
          {openBookings.length > 0 ? (
            <ul style={{ margin: 0, paddingLeft: "1rem", listStyle: "disc", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {openBookings.map((b) => (
                <li key={b.action_id} style={{ lineHeight: 1.45 }}>
                  <div style={{ fontWeight: 600, color: "#1e3a8a" }}>{formatTimeRangeLocal(b.start, b.end)}</div>
                  <div style={{ fontSize: "0.78rem", color: "#1e40af" }}>Patient: {b.patient_name}</div>
                  <div style={{ fontSize: "0.75rem", color: "#3b4f77", marginTop: 2 }}>{b.description}</div>
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ margin: 0, lineHeight: 1.45 }}>
              <span style={{ fontWeight: 600 }}>Shift on calendar: </span>
              {openShift}
            </p>
          )}
          <p style={{ margin: "0.5rem 0 0", fontSize: "0.7rem", color: "#64748b" }}>
            Visit times appear when the assigned action includes a schedule window. Otherwise only the day block is marked booked.
          </p>
        </div>
      )}
    </div>
  );
}

// ── Assignment list ───────────────────────────────────────────────────────────

const DOMAIN_PILL: Record<string, { bg: string; text: string; label: string }> = {
  health: { bg: "rgba(244, 63, 94, 0.12)", text: "#9f1239", label: "Health" },
  appointment: { bg: "rgba(56, 189, 248, 0.18)", text: "#0369a1", label: "Appointments" },
  grocery: { bg: "rgba(52, 211, 153, 0.18)", text: "#047857", label: "Grocery" },
  financial: { bg: "rgba(251, 191, 36, 0.22)", text: "#92400e", label: "Financial" },
};

/** Mirrors `agents/shared/db.py` when `domain` is blank (stale rows or legacy data). */
const MANUAL_TYPE_TO_DOMAIN: Record<string, string> = {
  cvs_refill: "health",
  pharmacy_refill: "health",
  health_refill: "health",
  appointment_booking: "appointment",
  book_appointment: "appointment",
  clinic_booking: "appointment",
  grocery_delivery: "grocery",
  instacart_cart: "grocery",
  grocery_setup: "grocery",
  supply_reorder: "grocery",
  amazon_order: "grocery",
  amazon_reorder: "grocery",
  caregiver_availability: "appointment",
  transport: "appointment",
  financial_assessment: "financial",
  caregiver_assignment: "appointment",
};

function inferAssignmentDomain(a: CaregiverAssignment): string {
  const raw = (a.domain ?? "").toLowerCase().trim();
  if (raw === "appointments" || raw === "appt" || raw === "appts") return "appointment";
  if (["health", "appointment", "grocery", "financial"].includes(raw)) return raw;
  const m = (a.manual_action_type ?? "").toLowerCase().replace(/[\s-]+/g, "_");
  if (m && MANUAL_TYPE_TO_DOMAIN[m]) return MANUAL_TYPE_TO_DOMAIN[m];
  const t = (a.type ?? "").toLowerCase();
  if (t === "scheduling" || t.includes("appointment") || ["clinic_visit", "check_in", "caregiver_scheduling"].includes(t)) {
    return "appointment";
  }
  if (t.includes("grocery") || t.includes("instacart")) return "grocery";
  if (t.includes("financ")) return "financial";
  return raw || "health";
}

const URGENCY_PILL: Record<string, { bg: string; text: string }> = {
  tier_0: { bg: "#ffe4e6", text: "#9f1239" },
  tier_1: { bg: "#fef2f2", text: "#991b1b" },
  tier_2: { bg: "#fffbeb", text: "#92400e" },
  tier_3: { bg: "#ecfdf5", text: "#065f46" },
  high: { bg: "#fef2f2", text: "#991b1b" },
  medium: { bg: "#fffbeb", text: "#92400e" },
  low: { bg: "#ecfdf5", text: "#065f46" },
};

function domainPill(domain: string | null | undefined) {
  const key = (domain ?? "").toLowerCase().trim();
  const c = DOMAIN_PILL[key] ?? {
    bg: "rgba(148, 163, 184, 0.2)",
    text: "#334155",
    label: key ? key.charAt(0).toUpperCase() + key.slice(1) : "Unknown",
  };
  return (
    <span
      style={{
        display: "inline-block",
        fontSize: "0.65rem",
        fontWeight: 700,
        letterSpacing: "0.04em",
        textTransform: "uppercase" as const,
        padding: "0.2rem 0.45rem",
        borderRadius: "4px",
        background: c.bg,
        color: c.text,
      }}
    >
      {c.label}
    </span>
  );
}

function urgencyPill(level: string | null | undefined) {
  if (!level) return null;
  const c = URGENCY_PILL[level] ?? { bg: "#f3f4f6", text: "#374151" };
  return (
    <span style={{ display: "inline-block", fontSize: "0.7rem", fontWeight: 600, padding: "0.2rem 0.5rem", borderRadius: "9999px", background: c.bg, color: c.text }}>
      {urgencyDisplayLabel(level)}
    </span>
  );
}

function AssignmentCard({ a }: { a: CaregiverAssignment }) {
  const review = a.review_by ? (formatReviewByLocal(a.review_by) ?? a.review_by) : null;
  const draft = (a.draft_content ?? "").trim();
  return (
    <div
      style={{
        border: "1px solid rgba(0,0,0,0.08)",
        borderRadius: "10px",
        background: "rgba(255, 255, 255, 0.7)",
        padding: "0.75rem 0.9rem",
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)",
      }}
    >
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", alignItems: "center", marginBottom: "0.5rem" }}>
        {domainPill(inferAssignmentDomain(a))}
        {urgencyPill(a.urgency_level ?? undefined)}
      </div>
      <div style={{ fontSize: "0.9rem", fontWeight: 600, color: "#111827", lineHeight: 1.35 }}>{a.description}</div>
      {review ? (
        <div style={{ fontSize: "0.75rem", color: "#0f766e", fontWeight: 500, marginTop: "0.4rem" }}>Review by: {review}</div>
      ) : null}
      <div style={{ fontSize: "0.8rem", color: "#6b7280", marginTop: "0.35rem" }}>Patient: {a.patient_name}</div>
      {draft ? (
        <div style={{ marginTop: "0.6rem" }}>
          <div style={{ fontSize: "0.62rem", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase" as const, color: "#6b7280", marginBottom: "0.3rem" }}>
            Action draft
          </div>
          <p
            style={{
              margin: 0,
              fontSize: "0.78rem",
              lineHeight: 1.5,
              color: "#374151",
              maxHeight: "7.5em",
              overflow: "auto",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word" as const,
              padding: "0.5rem 0.55rem",
              borderRadius: "6px",
              background: "rgba(249, 250, 251, 0.95)",
              border: "1px solid #e5e7eb",
            }}
          >
            {draft}
          </p>
        </div>
      ) : null}
    </div>
  );
}

function AssignmentList({ caregiverId }: { caregiverId: string }) {
  const { data: assignments = [], isLoading } = useGetCaregiverAssignmentsQuery(caregiverId);
  if (isLoading) return <p style={{ margin: 0, fontSize: "0.85rem", color: "#6b7280" }}>Loading assignments…</p>;
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
    <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      {assignments.map((a) => (
        <li key={a.action_id}>
          <AssignmentCard a={a} />
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
    <div style={{ boxSizing: "border-box", padding: "1.25rem 1.5rem 2rem", overflowY: "auto", height: "100%", background: PAGE_BG }}>
      <div style={{ width: "100%" }}>
        <header style={{ marginBottom: "1.25rem", paddingBottom: "1rem", borderBottom: "1px solid rgba(0, 0, 0, 0.08)" }}>
          <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.2rem", fontWeight: 700, color: "#111827", letterSpacing: "-0.02em" }}>
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
              <span style={{ display: "inline-block", fontSize: "0.75rem", fontWeight: 500, padding: "0.2rem 0.55rem", borderRadius: "9999px", background: "rgba(59, 130, 246, 0.12)", color: "#1d4ed8" }}>
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

// ── Add caregiver modal ───────────────────────────────────────────────────────

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

// ── Main view ─────────────────────────────────────────────────────────────────

const MIN_CARE_PX = 100;

export default function CaregiverManagement() {
  const location = useLocation();
  const navigate = useNavigate();
  const careHeaderRef = useRef<HTMLDivElement>(null);

  const actionId = new URLSearchParams(location.search).get("action_id");

  const { data: caregivers = [], isLoading } = useGetCaregiversQuery();
  const { data: actions = [] } = useGetActionsQuery();
  const [selectedCaregiver, setSelectedCaregiver] = useState<Caregiver | null>(null);
  const [showAddCaregiver, setShowAddCaregiver] = useState(false);

  const assignAction: Action | null = actionId
    ? (actions.find((a) => a.action_id === actionId) ?? null)
    : null;

  // Unused but kept to satisfy layout effect dependency shape
  useLayoutEffect(() => {}, [careHeaderRef]);

  return (
    <div style={{ display: "flex", height: "calc(100vh - 56px)" }}>
      {/* Left: caregiver list */}
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
          ref={careHeaderRef}
          style={{
            padding: "0.75rem 1rem",
            borderBottom: "1px solid #d1d5db",
            fontWeight: 600,
            fontSize: "0.95rem",
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
        <div style={{ flex: 1, minHeight: MIN_CARE_PX, overflow: "auto", background: PAGE_BG }}>
          {isLoading && <p style={{ padding: "0.75rem", fontSize: "0.85rem", color: "#6b7280" }}>Loading…</p>}
          {caregivers.map((c) => (
            <button
              key={c.caregiver_id}
              onClick={() => setSelectedCaregiver(c)}
              type="button"
              style={{
                display: "block",
                width: "100%",
                padding: "0.5rem 1rem",
                textAlign: "left",
                border: "none",
                borderBottom: "1px solid #d1d5db",
                background: selectedCaregiver?.caregiver_id === c.caregiver_id ? ROW_SELECTED : "transparent",
                cursor: "pointer",
                fontSize: "0.875rem",
              }}
              onMouseEnter={(ev) => {
                if (selectedCaregiver?.caregiver_id !== c.caregiver_id)
                  (ev.currentTarget as HTMLButtonElement).style.background = ROW_HOVER;
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

      {/* Right: assignment panel or caregiver detail */}
      <div style={{ flex: 1, overflow: "hidden", minHeight: 0, background: PAGE_BG }}>
        {assignAction ? (
          <AssignmentPanel
            action={assignAction}
            onClose={() => navigate("/caregivers")}
          />
        ) : selectedCaregiver ? (
          <CaregiverDetailPanel caregiver={selectedCaregiver} />
        ) : (
          <div style={{ boxSizing: "border-box", padding: "2rem 1.5rem", color: "#9ca3af", background: PAGE_BG, height: "100%" }}>
            <div style={{ width: "100%", fontSize: "0.9rem" }}>
              Select a caregiver to view details, or use "Schedule Task" on an action to assign it.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
