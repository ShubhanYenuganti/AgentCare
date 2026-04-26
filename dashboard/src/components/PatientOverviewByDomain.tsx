import { useNavigate } from "react-router-dom";
import type { Action, LifeGraph, Patient } from "../types";
import { DOMAIN_ORDER, domainLabel, groupPatientOverviewActions, type DomainKey } from "../utils/patientOverviewActions";
import { urgencyDisplayLabel } from "../utils/urgencyLabels";
import { formatLocal, formatReviewByLocal } from "../utils/formatActionDate";

const DOMAIN_ACCENT: Record<DomainKey, string> = {
  health: "#f43f5e",
  appointment: "#38bdf8",
  grocery: "#34d399",
  financial: "#fbbf24",
};

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
    <span
      style={{
        backgroundColor: c.bg,
        color: c.text,
        padding: "1px 6px",
        borderRadius: "9999px",
        fontSize: "0.65rem",
        fontWeight: 600,
        flexShrink: 0,
      }}
    >
      {urgencyDisplayLabel(level)}
    </span>
  );
}

function DomainOverviewStrip({ domain, patient }: { domain: DomainKey; patient: Patient }) {
  const lg = (patient.life_graph_json || {}) as LifeGraph;
  const prefs = patient.preferences_json || {};
  const lines: string[] = [];

  if (domain === "health") {
    const h = lg.health as Record<string, unknown> | undefined;
    if (h?.conditions && Array.isArray(h.conditions) && h.conditions.length)
      lines.push(`Conditions: ${(h.conditions as string[]).join(", ")}`);
    const meds = h?.medications as Array<{ name?: string; dose?: string; frequency?: string }> | undefined;
    if (meds?.length) {
      lines.push(
        `Meds: ${meds.map((m) => [m.name, m.dose].filter(Boolean).join(" ")).join("; ")}`
      );
    }
    if (typeof prefs.visit_time === "string" && prefs.visit_time) lines.push(`Visit preference: ${prefs.visit_time}`);
    if (typeof prefs.care_notes === "string" && prefs.care_notes) {
      const cn = prefs.care_notes.length > 140 ? `${prefs.care_notes.slice(0, 140)}…` : prefs.care_notes;
      lines.push(`Care note: ${cn}`);
    }
  }
  if (domain === "grocery") {
    const g = lg.grocery as Record<string, unknown> | undefined;
    const ld = g?.last_delivery != null && String(g.last_delivery).trim() ? String(g.last_delivery) : "—";
    lines.push(`Last delivery: ${ld}`);
    const staples = g?.staples;
    if (Array.isArray(staples) && staples.length) {
      const s = staples.map(String).join(", ");
      lines.push(s.length > 160 ? `${s.slice(0, 160)}…` : `Staples: ${s}`);
    }
    if (typeof prefs.grocery_delivery === "string" && prefs.grocery_delivery)
      lines.push(`Delivery: ${prefs.grocery_delivery}`);
    if (typeof prefs.diet_type === "string" && prefs.diet_type) lines.push(`Diet: ${prefs.diet_type}`);
    if (typeof prefs.dietary_restrictions === "string" && prefs.dietary_restrictions)
      lines.push(`Restrictions: ${prefs.dietary_restrictions}`);
  }
  if (domain === "financial") {
    const f = lg.financial as { bills?: Array<{ name?: string; amount?: number; due_date?: string }> } | undefined;
    if (f?.bills?.length) {
      lines.push(
        `Bills: ${f.bills.map((b) => `${b.name ?? "Bill"} $${b.amount ?? "—"} due ${b.due_date ?? "—"}`).join("; ")}`
      );
    } else {
      lines.push("No bills on file in life graph.");
    }
  }
  if (domain === "appointment") {
    const apps = lg.appointments;
    if (Array.isArray(apps) && apps.length) {
      lines.push(
        apps
          .slice(0, 3)
          .map((a: { date?: string; type?: string; provider?: string }) =>
            [a.date, a.type, a.provider].filter(Boolean).join(" — ")
          )
          .join(" · ")
      );
    } else {
      lines.push("No scheduled appointments in life graph.");
    }
    if (typeof prefs.visit_time === "string" && prefs.visit_time) lines.push(`Preference: ${prefs.visit_time}`);
  }

  if (lines.length === 0) {
    return (
      <p style={{ margin: 0, fontSize: "0.78rem", color: "#9ca3af" }}>No overview data for this domain yet.</p>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
      {lines.slice(0, 4).map((line, i) => (
        <p key={i} style={{ margin: 0, fontSize: "0.78rem", color: "#4b5563", lineHeight: 1.35 }}>
          {line}
        </p>
      ))}
    </div>
  );
}

function ActionCarouselRow({
  title,
  actions,
  emptyLabel,
  domain,
  patientName,
}: {
  title: string;
  actions: Action[];
  emptyLabel: string;
  domain: DomainKey;
  patientName: string;
}) {
  const accent = DOMAIN_ACCENT[domain];
  return (
    <div style={{ marginBottom: "0.6rem" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem", marginBottom: "0.35rem" }}>
        <span style={{ fontSize: "0.7rem", fontWeight: 600, color: "#6b7280", letterSpacing: "0.04em" }}>{title}</span>
        <span style={{ fontSize: "0.7rem", color: "#9ca3af" }}>({actions.length})</span>
      </div>
      <div
        style={{
          display: "flex",
          gap: "0.6rem",
          overflowX: "auto",
          paddingBottom: "0.25rem",
          marginLeft: "-2px",
          WebkitOverflowScrolling: "touch",
        }}
      >
        {actions.length === 0 ? (
          <p style={{ margin: 0, fontSize: "0.75rem", color: "#9ca3af", fontStyle: "italic" }}>{emptyLabel}</p>
        ) : (
          actions.map((a) => <PatientActionTile key={a.action_id} action={a} domain={domain} accent={accent} patientName={patientName} />)
        )}
      </div>
    </div>
  );
}

function PatientActionTile({
  action,
  domain: _d,
  accent,
  patientName,
}: {
  action: Action;
  domain: DomainKey;
  accent: string;
  patientName: string;
}) {
  const navigate = useNavigate();
  const detailText = action.draft_content?.trim() || action.description;
  const dateLine = (() => {
    if (action.completed) {
      const t = action.completion_date || action.created_at;
      return t ? `Completed: ${formatLocal(String(t))}` : null;
    }
    if (action.review_by) {
      const r = formatReviewByLocal(String(action.review_by));
      return r ? `Review by: ${r}` : null;
    }
    if (action.created_at) return `Created: ${formatLocal(String(action.created_at))}`;
    return null;
  })();
  return (
    <div
      style={{
        flex: "0 0 auto",
        width: "min(280px, 85vw)",
        height: 195,
        border: "1px solid #e5e7eb",
        borderRadius: "8px",
        background: "#fff",
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.05)",
        borderLeft: `3px solid ${accent}`,
        display: "flex",
        flexDirection: "column",
        padding: "0.5rem 0.6rem 0.5rem",
        boxSizing: "border-box",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", flexWrap: "wrap", flexShrink: 0 }}>
        <UrgencyPill level={action.urgency_level} />
        {action.is_overdue ? (
          <span style={{ fontSize: "0.6rem", fontWeight: 600, color: "#b91c1c" }}>Overdue</span>
        ) : null}
      </div>
      <div
        style={{
          flex: 1,
          minHeight: 0,
          marginTop: "0.35rem",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "0.35rem",
          paddingRight: "0.1rem",
        }}
      >
        <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "#111827", lineHeight: 1.3, flexShrink: 0 }}>{action.description}</div>
        <p style={{ margin: 0, fontSize: "0.72rem", color: "#6b7280", lineHeight: 1.35, wordBreak: "break-word" }}>{detailText}</p>
        {dateLine && (
          <div style={{ fontSize: "0.65rem", color: "#9ca3af", flexShrink: 0, paddingTop: "0.1rem" }}>{dateLine}</div>
        )}
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end", flexShrink: 0, paddingTop: "0.4rem" }}>
        <button
          type="button"
          onClick={() =>
            navigate(
              { pathname: "/actions", search: `?action=${encodeURIComponent(action.action_id)}` },
              { state: { highlightActionId: action.action_id, patientName } }
            )
          }
          data-testid={`open-in-feed-tile-${action.action_id}`}
          style={{
            padding: "0.25rem 0.6rem",
            background: "rgba(191, 219, 254, 0.7)",
            color: "#1e3a8a",
            border: "1px solid rgba(147, 197, 253, 0.9)",
            borderRadius: "6px",
            fontSize: "0.7rem",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Open in feed
        </button>
      </div>
    </div>
  );
}

function DomainBand({
  domain,
  patient,
  pending,
  completed,
  dismissed,
}: {
  domain: DomainKey;
  patient: Patient;
  pending: Action[];
  completed: Action[];
  dismissed: Action[];
}) {
  const label = domainLabel(domain);
  const total = pending.length + completed.length + dismissed.length;
  return (
    <section
      style={{
        marginBottom: "1.5rem",
        border: "1px solid #e5e7eb",
        borderRadius: "10px",
        background: "rgba(255, 255, 255, 0.85)",
        overflow: "hidden",
      }}
      aria-label={`${label} actions`}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0.6rem 0.9rem",
          background: "linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%)",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <h3 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 700, color: "#1e293b", letterSpacing: "0.02em" }}>{label}</h3>
        <span style={{ fontSize: "0.7rem", color: "#64748b" }}>{total} action{total === 1 ? "" : "s"}</span>
      </div>
      <div style={{ padding: "0.75rem 0.9rem 0.85rem" }}>
        <div style={{ marginBottom: "0.75rem" }}>
          <DomainOverviewStrip domain={domain} patient={patient} />
        </div>
        <ActionCarouselRow
          title="Pending"
          actions={pending}
          emptyLabel="No pending actions."
          domain={domain}
          patientName={patient.name}
        />
        <ActionCarouselRow
          title="Completed"
          actions={completed}
          emptyLabel="No completed actions."
          domain={domain}
          patientName={patient.name}
        />
        <ActionCarouselRow
          title="Dismissed"
          actions={dismissed}
          emptyLabel="No dismissed actions."
          domain={domain}
          patientName={patient.name}
        />
      </div>
    </section>
  );
}

function EmergencyStrip({ patient }: { patient: Patient }) {
  const raw = patient.life_graph_json;
  const contacts = (raw as LifeGraph)?.emergency_contacts;
  if (!Array.isArray(contacts) || contacts.length === 0) return null;
  return (
    <section
      style={{
        marginTop: "0.5rem",
        padding: "0.65rem 0.9rem",
        background: "#fffbeb",
        border: "1px solid #fde68a",
        borderRadius: "8px",
        fontSize: "0.78rem",
        color: "#713f12",
      }}
    >
      <strong style={{ display: "block", marginBottom: "0.35rem" }}>Emergency contacts</strong>
      <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
        {contacts.map((c, i) => (
          <li key={i}>
            {c.name} ({c.relationship}) — {c.phone}
          </li>
        ))}
      </ul>
    </section>
  );
}

type Props = {
  patient: Patient;
  feedActions: Action[];
};

export default function PatientOverviewByDomain({ patient, feedActions }: Props) {
  const pendingRaw = (patient as Patient & { pending_actions?: Record<string, unknown>[] }).pending_actions ?? [];
  const historyRaw = (patient as Patient & { action_history?: Record<string, unknown>[] }).action_history ?? [];

  const byDomain = groupPatientOverviewActions(pendingRaw, historyRaw, feedActions, patient.patient_id, patient.name);

  return (
    <div>
      {DOMAIN_ORDER.map((d) => (
        <DomainBand
          key={d}
          domain={d}
          patient={patient}
          pending={byDomain[d].pending}
          completed={byDomain[d].completed}
          dismissed={byDomain[d].dismissed}
        />
      ))}
      <EmergencyStrip patient={patient} />
    </div>
  );
}
