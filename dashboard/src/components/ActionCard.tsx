import { useState, useEffect, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import type { Action, ExecutionPlanStep } from "../types";
import { formatReviewByLocal } from "../utils/formatActionDate";
import { canonicalAutomationRoute, formatAutomationStepTitle } from "../utils/automationStepLabels";
import { urgencyDisplayLabel } from "../utils/urgencyLabels";
import { useApproveActionMutation, useDismissActionMutation } from "../api/client";
import ActionChatPanel from "./ActionChatPanel";
import DraftModal from "./DraftModal";
import Toast from "./Toast";

interface Props {
  action: Action;
  /** Hides Approve / Dismiss / Ask / Modify / View scheduling; shows a single “open feed” control. */
  readOnly?: boolean;
  /** Emphasize this card (e.g. when deep-linked from the patient view). */
  highlighted?: boolean;
}

const URGENCY: Record<string, { accent: string; labelBg: string; labelText: string }> = {
  tier_0: { accent: "#e11d48", labelBg: "rgba(254, 205, 211, 0.65)", labelText: "#9f1239" },
  tier_1: { accent: "#f43f5e", labelBg: "rgba(254, 215, 170, 0.55)", labelText: "#9a3412" },
  tier_2: { accent: "#d97706", labelBg: "rgba(254, 240, 138, 0.5)", labelText: "#854d0e" },
  tier_3: { accent: "#059669", labelBg: "rgba(167, 243, 208, 0.55)", labelText: "#065f46" },
  high: { accent: "#f43f5e", labelBg: "rgba(254, 215, 170, 0.55)", labelText: "#9a3412" },
  medium: { accent: "#d97706", labelBg: "rgba(254, 240, 138, 0.5)", labelText: "#854d0e" },
  low: { accent: "#059669", labelBg: "rgba(167, 243, 208, 0.55)", labelText: "#065f46" },
};

const DOMAIN: Record<string, string> = {
  health: "#f43f5e",
  appointment: "#38bdf8",
  grocery: "#34d399",
  financial: "#fbbf24",
};

function urgencyStyle(level: string) {
  return URGENCY[level] ?? { accent: "#6b7280", labelBg: "rgba(229, 231, 235, 0.9)", labelText: "#1f2937" };
}

type CardVariant = "health-modify" | "qa";

function getVariant(action: Action): CardVariant {
  if (action.domain === "health" && action.draft_content) return "health-modify";
  return "qa";
}

const BTN_BLUE: CSSProperties = {
  background: "rgba(191, 219, 254, 0.75)",
  color: "#0a0a0a",
  border: "1px solid rgba(147, 197, 253, 0.95)",
};

/** Direction 2: shared neutral row; chroma only on Approve (green) / Dismiss (red) via left edge */
/** Strips native bevel/inner ring on macOS that fights custom borders/shadows */
const BTN_RESET: CSSProperties = {
  WebkitAppearance: "none",
  appearance: "none",
};

const BTN_ROW_BASE: CSSProperties = {
  ...BTN_RESET,
  minWidth: "7.5rem",
  padding: "0.45rem 0.9rem",
  borderRadius: "9999px",
  fontSize: "0.8rem",
  fontWeight: 600,
  textAlign: "center" as const,
  backgroundColor: "#f3f4f6",
  color: "#374151",
  border: "1px solid #e5e7eb",
  boxSizing: "border-box" as const,
  cursor: "pointer",
  boxShadow: "0 1px 2px rgba(15, 23, 42, 0.06)",
};

const BTN_ROW_DISABLED: CSSProperties = {
  ...BTN_ROW_BASE,
  background: "rgba(209, 213, 219, 0.65)",
  color: "#9ca3af",
  border: "1px solid #d1d5db",
  cursor: "not-allowed",
  opacity: 0.95,
  backgroundImage: "none",
  boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)",
};

/** Left bar via padding-box gradient (avoids 1px vs 3px border radius artifacts) + uniform soft shadow */
const BTN_ROW_APPROVE: CSSProperties = {
  ...BTN_ROW_BASE,
  color: "#065f46",
  border: "1px solid #047857",
  backgroundImage: "linear-gradient(90deg, #10b981 0, #10b981 3px, #f3f4f6 3px, #f3f4f6 100%)",
  backgroundOrigin: "padding-box",
  backgroundClip: "padding-box",
  boxShadow: "0 1px 2px rgba(6, 78, 59, 0.12), 0 1px 3px rgba(6, 78, 59, 0.06)",
};

const BTN_ROW_DISMISS: CSSProperties = {
  ...BTN_ROW_BASE,
  color: "#991b1b",
  border: "1px solid #991b1b",
  backgroundImage: "linear-gradient(90deg, #f87171 0, #f87171 3px, #f3f4f6 3px, #f3f4f6 100%)",
  backgroundOrigin: "padding-box",
  backgroundClip: "padding-box",
  boxShadow: "0 1px 2px rgba(127, 29, 29, 0.12), 0 1px 3px rgba(127, 29, 29, 0.06)",
};

const glass: CSSProperties = {
  position: "relative",
  borderRadius: "20px",
  background: "#f5f6f8",
  border: "1px solid #d1d5db",
  boxShadow: "0 4px 18px rgba(0, 0, 0, 0.06)",
  overflow: "hidden",
  color: "#0a0a0a",
};

const section: CSSProperties = {
  marginTop: "0.85rem",
  padding: "0.75rem 0.9rem",
  borderRadius: "12px",
  background: "rgba(255, 255, 255, 0.75)",
  border: "1px solid #e5e7eb",
  fontSize: "0.8rem",
  lineHeight: 1.5,
  color: "#111827",
};

const sectionLabel: CSSProperties = {
  fontSize: "0.65rem",
  fontWeight: 600,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: "#4b5563",
  marginBottom: "0.4rem",
};

const mono: CSSProperties = {
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
  fontSize: "0.75rem",
  color: "#1f2937",
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
  maxHeight: "160px",
  overflow: "auto",
  margin: 0,
};

function plannedStepLine(s: ExecutionPlanStep) {
  const err = s.preflight_errors?.length;
  const main = formatAutomationStepTitle(s);
  if (err) return `${main} · ${err} preflight issue${err === 1 ? "" : "s"}`;
  return main;
}

/** Matches `agents/shared/notifications.py` default Resend from address. */
const DEFAULT_SENDER_EMAIL = "noreply@notifications.macos-care.ai";

const emailInboxShell: CSSProperties = {
  border: "1px solid #d1d5db",
  borderRadius: "10px",
  background: "#fff",
  overflow: "hidden",
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.8)",
};

const emailMetaRow: CSSProperties = {
  fontSize: "0.78rem",
  color: "#1f2937",
  lineHeight: 1.4,
  padding: "0.35rem 0.75rem",
  borderBottom: "1px solid #e5e7eb",
};

const emailBodyBox: CSSProperties = {
  padding: "0.75rem 0.75rem 0.85rem",
  fontSize: "0.8rem",
  lineHeight: 1.55,
  color: "#111827",
  maxHeight: "220px",
  overflow: "auto",
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
  fontFamily: "inherit",
  margin: 0,
};

export default function ActionCard({ action, readOnly = false, highlighted = false }: Props) {
  const [chatOpen, setChatOpen] = useState(false);
  const [draftOpen, setDraftOpen] = useState(false);
  const [modifying, setModifying] = useState(false);
  const navigate = useNavigate();
  const [approveAction, { isLoading: approving }] = useApproveActionMutation();
  const [dismissAction, { isLoading: dismissing }] = useDismissActionMutation();
  const actionPending = approving || dismissing;

  useEffect(() => {
    if (modifying && !action.modification_in_progress) {
      setModifying(false);
    }
  }, [action.modification_in_progress, modifying]);

  const variant = getVariant(action);
  const u = urgencyStyle(action.urgency_level);
  const isLocked = Boolean(action.modification_in_progress);
  const reviewLine = formatReviewByLocal(action.review_by);
  const domainColor = DOMAIN[action.domain] ?? "#94a3b8";
  const plan = action.execution_plan;
  const emailTo = action.recipient_email?.trim() || "";
  const emailSubj = (action.email_subject ?? "").trim();
  const emailBody = (action.draft_content ?? action.description ?? "").trim();
  const isEmailAction =
    Boolean(emailTo) ||
    Boolean(emailSubj) ||
    /email/i.test(String(action.type ?? ""));

  const showEmailInbox = isEmailAction;
  const showPlainDraftBlock = Boolean(action.draft_content) && !isEmailAction;

  return (
    <>
      <div
        data-testid="action-card"
        id={`action-focus-${action.action_id}`}
        style={{
          ...glass,
          ...(highlighted
            ? {
                boxShadow: "0 0 0 3px rgba(59, 130, 246, 0.45), 0 4px 18px rgba(0, 0, 0, 0.08)",
              }
            : {}),
        }}
      >
        {Boolean(action.is_overdue) && (
          <div
            data-testid="overdue-banner"
            style={{
              textAlign: "center",
              fontSize: "0.65rem",
              fontWeight: 700,
              letterSpacing: "0.18em",
              padding: "6px 0",
              background: "rgba(254, 202, 202, 0.55)",
              color: "#1f2937",
              borderBottom: "1px solid rgba(248, 113, 113, 0.35)",
            }}
          >
            OVERDUE
          </div>
        )}

        <div
          style={{
            padding: "1.1rem 1.2rem 1.15rem",
            paddingTop: action.is_overdue ? "1rem" : "1.2rem",
            borderLeft: `4px solid ${u.accent}`,
          }}
        >
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: "0.6rem",
              marginBottom: "0.75rem",
            }}
          >
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", alignItems: "center" }}>
              <span
                style={{
                  backgroundColor: `${domainColor}18`,
                  color: "#0a0a0a",
                  padding: "3px 10px",
                  borderRadius: "9999px",
                  fontSize: "0.68rem",
                  fontWeight: 600,
                  textTransform: "capitalize",
                  border: `1px solid ${domainColor}40`,
                }}
              >
                {action.domain}
              </span>
              <span
                style={{
                  backgroundColor: u.labelBg,
                  color: u.labelText,
                  padding: "3px 10px",
                  borderRadius: "9999px",
                  fontSize: "0.68rem",
                  fontWeight: 600,
                  border: `1px solid ${u.accent}44`,
                }}
              >
                {urgencyDisplayLabel(action.urgency_level)}
              </span>
            </div>

            {action.patient_name && (
              <div style={{ textAlign: "right", minWidth: "min(100%, 200px)" }}>
                <div style={{ fontSize: "0.65rem", fontWeight: 600, letterSpacing: "0.1em", color: "#4b5563" }}>
                  Patient
                </div>
                <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "#0a0a0a" }}>{action.patient_name}</div>
              </div>
            )}
          </div>

          <p
            style={{
              margin: "0 0 0.5rem",
              fontSize: "1rem",
              fontWeight: 600,
              lineHeight: 1.45,
              color: "#0a0a0a",
            }}
          >
            {action.description}
          </p>

          {reviewLine && (
            <p style={{ margin: "0 0 0.25rem", fontSize: "0.82rem", color: "#4b5563" }}>
              Review by <span style={{ color: "#0a0a0a" }}>{reviewLine}</span>
            </p>
          )}

          {showPlainDraftBlock && (
            <div style={section}>
              <div style={sectionLabel}>Action draft</div>
              <p style={{ ...mono, maxHeight: "200px" }}>{action.draft_content}</p>
            </div>
          )}

          {showEmailInbox && (
            <div style={section}>
              <div style={sectionLabel}>Draft email</div>
              <div style={emailInboxShell}>
                <div style={emailMetaRow}>
                  <span style={{ color: "#6b7280", marginRight: "0.5rem" }}>From</span>
                  <span
                    style={{
                      fontFamily: "ui-monospace, Menlo, Consolas, monospace",
                      fontSize: "0.76rem",
                      color: "#0a0a0a",
                    }}
                  >
                    {DEFAULT_SENDER_EMAIL}
                  </span>
                </div>
                {emailTo ? (
                  <div style={emailMetaRow}>
                    <span style={{ color: "#6b7280", marginRight: "0.5rem" }}>To</span>
                    <span
                      style={{
                        fontFamily: "ui-monospace, Menlo, Consolas, monospace",
                        fontSize: "0.76rem",
                        color: "#0a0a0a",
                      }}
                    >
                      {emailTo}
                    </span>
                    {action.recipient_type ? (
                      <span style={{ marginLeft: "0.5rem", fontSize: "0.7rem", color: "#6b7280" }}>
                        ({action.recipient_type})
                      </span>
                    ) : null}
                  </div>
                ) : null}
                <div
                  style={{
                    ...emailMetaRow,
                    borderBottom: "1px solid #e5e7eb",
                    fontWeight: 600,
                    paddingBottom: "0.45rem",
                  }}
                >
                  <span style={{ color: "#6b7280", marginRight: "0.5rem", fontWeight: 500 }}>Subject</span>
                  <span style={{ color: "#0a0a0a" }}>{emailSubj || "—"}</span>
                </div>
                <p style={emailBodyBox}>{emailBody || "—"}</p>
              </div>
            </div>
          )}

          {plan && plan.steps.length > 0 && (
            <div style={section}>
              <div style={sectionLabel}>Planned automation</div>
              <ol style={{ margin: 0, paddingLeft: "1.1rem", color: "#111827" }}>
                {plan.steps.map((s, i) => (
                  <li
                    key={`${s.kind}-${s.route}-${i}`}
                    style={{ marginBottom: "0.25rem", fontSize: "0.8rem", lineHeight: 1.45, color: "#111827" }}
                    title={canonicalAutomationRoute(s)}
                  >
                    {plannedStepLine(s)}
                    {s.preflight_errors && s.preflight_errors.length > 0 && (
                      <pre style={{ ...mono, marginTop: "0.35rem", maxHeight: "80px", fontSize: "0.68rem" }}>
                        {s.preflight_errors.join("\n")}
                      </pre>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {readOnly ? (
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "1rem" }}>
              <button
                type="button"
                onClick={() =>
                  navigate(
                    { pathname: "/actions", search: `?action=${encodeURIComponent(action.action_id)}` },
                    { state: { highlightActionId: action.action_id } }
                  )
                }
                data-testid="open-in-feed-btn"
                style={{
                  padding: "0.45rem 1rem",
                  ...BTN_BLUE,
                  borderRadius: "9999px",
                  cursor: "pointer",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                }}
                title="Open this action in the full Action Feed"
              >
                Open in Action Feed
              </button>
            </div>
          ) : (
            <div
              style={{
                display: "flex",
                gap: "0.5rem",
                flexWrap: "wrap",
                marginTop: "1rem",
                alignItems: "center",
                justifyContent: "flex-start",
              }}
            >
              {variant === "health-modify" && (
                <>
                  <button
                    onClick={() => setDraftOpen(true)}
                    disabled={isLocked || actionPending}
                    data-testid="modify-draft-btn"
                    type="button"
                    style={isLocked || actionPending ? BTN_ROW_DISABLED : BTN_ROW_BASE}
                  >
                    {isLocked ? "Modification in progress…" : "Modify Draft"}
                  </button>
                  <button
                    onClick={() => setChatOpen(true)}
                    disabled={actionPending}
                    data-testid="ask-btn"
                    type="button"
                    style={actionPending ? BTN_ROW_DISABLED : BTN_ROW_BASE}
                  >
                    Ask
                  </button>
                </>
              )}

              {variant === "qa" && (
                <button
                  onClick={() => setChatOpen(true)}
                  disabled={actionPending}
                  data-testid="ask-btn"
                  type="button"
                  style={actionPending ? BTN_ROW_DISABLED : BTN_ROW_BASE}
                >
                  Ask
                </button>
              )}

              <button
                onClick={() => approveAction(action.action_id)}
                disabled={actionPending}
                data-testid="approve-btn"
                type="button"
                style={actionPending ? BTN_ROW_DISABLED : BTN_ROW_APPROVE}
              >
                {approving ? "Approving…" : "Approve"}
              </button>
              <button
                onClick={() => dismissAction(action.action_id)}
                disabled={actionPending}
                data-testid="dismiss-btn"
                type="button"
                style={actionPending ? BTN_ROW_DISABLED : BTN_ROW_DISMISS}
              >
                {dismissing ? "Dismissing…" : "Dismiss"}
              </button>

              {action.completed === 0 && !action.assigned_caregiver && Boolean(action.manual_action_type) && (
                <button
                  onClick={() => navigate(`/caregivers?action_id=${encodeURIComponent(action.action_id)}`)}
                  data-testid="schedule-task-btn"
                  type="button"
                  style={BTN_ROW_BASE}
                >
                  Schedule Task
                </button>
              )}
            </div>
          )}

          {chatOpen && <ActionChatPanel action={action} onClose={() => setChatOpen(false)} />}
        </div>
      </div>
      {draftOpen && (
        <DraftModal
          action={action}
          onClose={() => setDraftOpen(false)}
          onSubmitted={() => { setDraftOpen(false); setModifying(true); }}
        />
      )}
      {modifying && <Toast message="Modifying draft…" />}
    </>
  );
}
