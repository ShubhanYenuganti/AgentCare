import type { CSSProperties } from "react";
import { useState } from "react";
import {
  useGetOrgQuery,
  useUpdateOrgMutation,
  useGetActionsQuery,
  useGetCaregiversQuery,
  useGetPatientsQuery,
} from "../api/client";
import type { Caregiver, OrgProfile } from "../types";

const PAGE_SHEET: CSSProperties = {
  minHeight: "calc(100vh - 56px)",
  width: "100%",
  background: "#e8eaed",
  boxSizing: "border-box",
};

const PAGE_INNER: CSSProperties = {
  maxWidth: "1000px",
  margin: "0 auto",
  padding: "1.5rem clamp(1rem, 3vw, 1.5rem) 2.5rem",
  boxSizing: "border-box",
};

const SECTION_LABEL: CSSProperties = {
  fontSize: "0.7rem",
  fontWeight: 600,
  letterSpacing: "0.1em",
  textTransform: "uppercase" as const,
  color: "#6b7280",
  margin: "0 0 0.75rem",
};

const BTN_EDIT: CSSProperties = {
  padding: "0.5rem 1.1rem",
  background: "rgba(191, 219, 254, 0.75)",
  color: "#0a0a0a",
  border: "1px solid rgba(147, 197, 253, 0.95)",
  borderRadius: "9999px",
  cursor: "pointer",
  fontSize: "0.875rem",
  fontWeight: 500,
  whiteSpace: "nowrap" as const,
  flexShrink: 0,
};

const PROTOCOL_DOMAIN_COLOR: Record<string, string> = {
  health: "#f43f5e",
  appointment: "#38bdf8",
  grocery: "#34d399",
  financial: "#fbbf24",
  scheduling: "#6366f1",
};

function domainDotColor(domain: string | undefined): string {
  const d = (domain ?? "").toLowerCase();
  return PROTOCOL_DOMAIN_COLOR[d] ?? "#94a3b8";
}

function initialsFromName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  if (parts.length === 1 && parts[0].length >= 2) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  return parts[0]?.[0]?.toUpperCase() ?? "?";
}

// ── Metric card ───────────────────────────────────────────────────────────────

function MetricCard({
  label,
  value,
  color,
  caption,
}: {
  label: string;
  value: string | number;
  color?: string;
  caption: string;
}) {
  return (
    <div
      className="org-metric-card"
      style={{
        border: "1px solid #e5e7eb",
        borderRadius: "12px",
        padding: "1rem 1.25rem",
        backgroundColor: "#f0f2f5",
        borderTop: color ? `3px solid ${color}` : undefined,
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)",
      }}
    >
      <p
        style={{
          margin: "0 0 0.25rem",
          fontSize: "0.7rem",
          color: "#6b7280",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          fontWeight: 600,
        }}
      >
        {label}
      </p>
      <p style={{ margin: "0 0 0.35rem", fontSize: "1.5rem", fontWeight: 600, color: "#111827" }}>{value}</p>
      <p style={{ margin: 0, fontSize: "0.72rem", lineHeight: 1.4, color: "#9ca3af" }}>{caption}</p>
    </div>
  );
}

function StatusPill({ children, kind }: { children: string; kind: "positive" | "neutral" | "amber" | "count" }) {
  const styles: Record<string, CSSProperties> = {
    positive: { background: "rgba(16, 185, 129, 0.12)", color: "#047857" },
    neutral: { background: "rgba(107, 114, 128, 0.12)", color: "#4b5563" },
    amber: { background: "rgba(245, 158, 11, 0.15)", color: "#b45309" },
    count: { background: "rgba(99, 102, 241, 0.1)", color: "#4338ca" },
  };
  return (
    <span
      style={{
        display: "inline-block",
        fontSize: "0.72rem",
        fontWeight: 600,
        padding: "0.2rem 0.5rem",
        borderRadius: "9999px",
        ...styles[kind],
      }}
    >
      {children}
    </span>
  );
}

// ── Edit Org Profile form (task 6.5) ──────────────────────────────────────────

function EditOrgModal({ org, onClose }: { org: OrgProfile; onClose: () => void }) {
  const [form, setForm] = useState({
    org_name: org.org_name ?? "",
    care_philosophy: org.care_philosophy ?? "",
    escalation_chain: org.escalation_chain ?? "",
    escalation_lead: org.escalation_lead ?? "",
  });
  const [updateOrg, { isLoading }] = useUpdateOrgMutation();

  const handleSubmit = async () => {
    await updateOrg(form);
    onClose();
  };

  return (
    <>
      <div onClick={onClose} style={{ position: "fixed", inset: 0, backgroundColor: "rgba(0,0,0,0.4)", zIndex: 60 }} />
      <div
        style={{
          position: "fixed",
          top: "50%",
          left: "50%",
          transform: "translate(-50%,-50%)",
          width: "500px",
          maxWidth: "95vw",
          backgroundColor: "#fff",
          borderRadius: "12px",
          boxShadow: "0 20px 60px rgba(0,0,0,0.2)",
          zIndex: 70,
        }}
      >
        <div
          style={{
            padding: "1.25rem 1.5rem",
            borderBottom: "1px solid #e5e7eb",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>Edit Org Profile</h2>
          <button
            onClick={onClose}
            style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1.25rem", color: "#6b7280" }}
          >
            ×
          </button>
        </div>
        <div style={{ padding: "1.25rem 1.5rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {(["org_name", "care_philosophy", "escalation_chain", "escalation_lead"] as const).map((field) => (
            <div key={field}>
              <label
                style={{ display: "block", fontSize: "0.8rem", fontWeight: 500, marginBottom: "0.25rem", color: "#374151" }}
              >
                {field.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
              </label>
              <input
                value={form[field]}
                onChange={(e) => setForm((f) => ({ ...f, [field]: e.target.value }))}
                style={{
                  width: "100%",
                  border: "1px solid #d1d5db",
                  borderRadius: "8px",
                  padding: "0.5rem",
                  fontSize: "0.875rem",
                  boxSizing: "border-box",
                }}
              />
            </div>
          ))}
        </div>
        <div
          style={{ padding: "1rem 1.5rem", borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}
        >
          <button
            onClick={onClose}
            style={{
              padding: "0.5rem 1rem",
              border: "1px solid #d1d5db",
              borderRadius: "8px",
              background: "#fff",
              cursor: "pointer",
              fontSize: "0.875rem",
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={isLoading}
            style={{
              padding: "0.5rem 1.25rem",
              background: "rgba(191, 219, 254, 0.9)",
              color: "#0a0a0a",
              border: "1px solid rgba(147, 197, 253, 0.95)",
              borderRadius: "8px",
              cursor: "pointer",
              fontSize: "0.875rem",
              fontWeight: 500,
              opacity: isLoading ? 0.6 : 1,
            }}
          >
            {isLoading ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </>
  );
}

// ── Caregiver row ─────────────────────────────────────────────────────────────

function CaregiverRow({ c }: { c: Caregiver }) {
  const n = c.assignments?.length ?? 0;
  return (
    <div
      className="org-caregiver-row"
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.75rem",
        padding: "0.75rem 1rem",
        background: "#f0f2f5",
        borderRadius: "12px",
        border: "1px solid rgba(15, 23, 42, 0.07)",
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)",
      }}
    >
      <div
        style={{
          width: "40px",
          height: "40px",
          borderRadius: "50%",
          background: "linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%)",
          color: "#3730a3",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "0.8rem",
          fontWeight: 700,
          flexShrink: 0,
        }}
        aria-hidden
      >
        {initialsFromName(c.name)}
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontWeight: 600, fontSize: "0.9rem", color: "#111827" }}>{c.name}</div>
        <div style={{ fontSize: "0.72rem", color: "#9ca3af", marginTop: "0.15rem" }}>Caregiver</div>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", justifyContent: "flex-end" }}>
        {c.availability_today ? (
          <StatusPill kind="positive">Available</StatusPill>
        ) : (
          <StatusPill kind="neutral">Unavailable</StatusPill>
        )}
        {c.booked_today ? <StatusPill kind="amber">Booked</StatusPill> : <StatusPill kind="neutral">Not booked</StatusPill>}
        <StatusPill kind="count">{`${n} assignment${n === 1 ? "" : "s"}`}</StatusPill>
      </div>
    </div>
  );
}

// ── Main view ─────────────────────────────────────────────────────────────────

export default function OrgDashboard() {
  const [editOpen, setEditOpen] = useState(false);
  const { data: org, isLoading: orgLoading } = useGetOrgQuery();
  const { data: actions = [] } = useGetActionsQuery();
  const { data: caregivers = [] } = useGetCaregiversQuery();
  const { data: patients = [] } = useGetPatientsQuery();

  const totalPending = actions.filter((a) => !a.completed).length;
  const totalOverdue = actions.filter((a) => Boolean(a.is_overdue)).length;
  const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 3600 * 1000).toISOString();
  const recent = actions.filter((a) => a.created_at && a.created_at >= thirtyDaysAgo);
  const completionRate =
    recent.length > 0 ? Math.round((recent.filter((a) => a.completed).length / recent.length) * 100) : 0;
  const urgencyScores: Record<string, number> = {
    tier_0: 4,
    tier_1: 3,
    tier_2: 2,
    tier_3: 1,
    high: 3,
    medium: 2,
    low: 1,
  };
  const avgUrgency =
    actions.length > 0
      ? (
          actions.reduce((sum, a) => sum + (urgencyScores[a.urgency_level] ?? 1), 0) / actions.length
        ).toFixed(1)
      : "—";

  const protocols: Array<{ name: string; description: string; domain: string }> = org?.protocols ?? [];

  if (orgLoading) {
    return (
      <div style={{ ...PAGE_SHEET, padding: "1.5rem", color: "#6b7280" }}>
        Loading…
      </div>
    );
  }

  return (
    <div style={PAGE_SHEET}>
      <div style={PAGE_INNER}>
        {/* Hero — org summary */}
        <div
          style={{
            background: "#f2f4f7",
            borderRadius: "16px",
            padding: "1.35rem 1.5rem",
            border: "1px solid rgba(15, 23, 42, 0.07)",
            boxShadow: "0 1px 3px rgba(15, 23, 42, 0.04)",
            marginBottom: "1.25rem",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: "1rem",
            flexWrap: "wrap",
          }}
        >
          <div style={{ minWidth: 0, flex: "1 1 220px" }}>
            <p style={{ margin: "0 0 0.2rem", fontSize: "0.68rem", fontWeight: 600, letterSpacing: "0.12em", color: "#9ca3af" }}>
              ORGANISATION
            </p>
            <h1 style={{ margin: "0 0 0.35rem", fontSize: "1.35rem", fontWeight: 600, color: "#0a0a0a", letterSpacing: "-0.02em" }}>
              {org?.org_name ?? "Organisation"}
            </h1>
            <p style={{ margin: 0, fontSize: "0.85rem", color: "#6b7280" }}>
              {protocols.length} protocols · {caregivers.length} caregivers · {patients.length} patients
            </p>
            {org?.care_philosophy && (
              <blockquote
                style={{
                  margin: "0.85rem 0 0",
                  padding: "0 0 0 0.9rem",
                  borderLeft: "3px solid rgba(59, 130, 246, 0.5)",
                  fontSize: "0.88rem",
                  color: "#374151",
                  lineHeight: 1.5,
                }}
              >
                {org.care_philosophy}
              </blockquote>
            )}
          </div>
          <button type="button" onClick={() => setEditOpen(true)} style={BTN_EDIT}>
            Edit Org Profile
          </button>
        </div>

        {/* Metrics */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "0.75rem",
            marginBottom: "1.5rem",
          }}
        >
          <MetricCard
            label="Pending actions"
            value={totalPending}
            color="#f59e0b"
            caption="Open items that still need a review or action."
          />
          <MetricCard
            label="Overdue actions"
            value={totalOverdue}
            color="#ef4444"
            caption="Past their review-by time; highest attention."
          />
          <MetricCard
            label="30-day completion"
            value={`${completionRate}%`}
            color="#10b981"
            caption="Share of recent actions completed within 30 days."
          />
          <MetricCard
            label="Avg urgency score"
            value={avgUrgency}
            color="#6366f1"
            caption="Weighted by tier (tier 0 = 4, … tier 3 = 1)."
          />
        </div>

        {/* Protocols — always show section; empty state when none */}
        <section style={{ marginBottom: "1.5rem" }}>
          <h2 style={SECTION_LABEL}>Protocols</h2>
          {protocols.length > 0 ? (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
                gap: "0.75rem",
              }}
            >
              {protocols.map((p, i) => {
                const dot = domainDotColor(p.domain);
                return (
                  <div
                    key={i}
                    className="org-protocol-card"
                    style={{
                      border: "1px solid rgba(15, 23, 42, 0.08)",
                      borderRadius: "12px",
                      padding: "0.9rem 1rem",
                      background: "#f0f2f5",
                      boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)",
                    }}
                  >
                    <div
                      style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.45rem" }}
                    >
                      <span
                        style={{
                          width: "8px",
                          height: "8px",
                          borderRadius: "50%",
                          background: dot,
                          flexShrink: 0,
                        }}
                        title={p.domain}
                      />
                      <span style={{ fontWeight: 600, fontSize: "0.875rem" }}>{p.name}</span>
                    </div>
                    {p.domain && (
                      <div style={{ marginBottom: "0.35rem" }}>
                        <span
                          style={{
                            fontSize: "0.65rem",
                            fontWeight: 600,
                            padding: "1px 7px",
                            borderRadius: "9999px",
                            background: `${dot}15`,
                            color: "#1f2937",
                            textTransform: "capitalize" as const,
                          }}
                        >
                          {p.domain}
                        </span>
                      </div>
                    )}
                    <p style={{ margin: 0, fontSize: "0.8rem", color: "#6b7280", lineHeight: 1.5 }}>{p.description}</p>
                  </div>
                );
              })}
            </div>
          ) : (
            <div
              style={{
                border: "1px dashed rgba(15, 23, 42, 0.12)",
                borderRadius: "12px",
                padding: "1.25rem 1.35rem",
                background: "rgba(240, 242, 245, 0.85)",
                fontSize: "0.85rem",
                color: "#6b7280",
                lineHeight: 1.5,
              }}
            >
              No protocols are configured for this organisation yet. When your backend supplies protocol records, they will
              appear here. You can still update org details via <strong style={{ color: "#374151" }}>Edit Org Profile</strong>
              .
            </div>
          )}
        </section>

        {/* Caregiver roster */}
        <section>
          <h2 style={SECTION_LABEL}>Caregiver roster</h2>
          {caregivers.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {caregivers.map((c) => (
                <CaregiverRow key={c.caregiver_id} c={c} />
              ))}
            </div>
          ) : (
            <div
              style={{
                border: "1px dashed rgba(15, 23, 42, 0.12)",
                borderRadius: "12px",
                padding: "1.25rem",
                background: "rgba(240, 242, 245, 0.85)",
                fontSize: "0.85rem",
                color: "#6b7280",
              }}
            >
              No caregivers in this org yet.
            </div>
          )}
        </section>
      </div>

      {editOpen && org && <EditOrgModal org={org} onClose={() => setEditOpen(false)} />}
    </div>
  );
}
