import type { Action, ExecutionPlan } from "../types";

export type DomainKey = "health" | "grocery" | "financial" | "appointment";

export const DOMAIN_ORDER: DomainKey[] = ["health", "grocery", "financial", "appointment"];

const DOMAIN_LABEL: Record<DomainKey, string> = {
  health: "Health",
  grocery: "Grocery",
  financial: "Financial",
  appointment: "Appointments",
};

export function domainLabel(d: DomainKey): string {
  return DOMAIN_LABEL[d];
}

export function normalizeDomain(raw: string | undefined | null): DomainKey {
  const s = (raw ?? "health").toLowerCase();
  if (s === "grocery") return "grocery";
  if (s === "financial") return "financial";
  if (s === "appointment" || s === "appointments") return "appointment";
  return "health";
}

export function coalesceRecordToAction(
  raw: Record<string, unknown>,
  patientId: string,
  patientName: string
): Action {
  return {
    action_id: String(raw.action_id),
    patient_id: String(raw.patient_id ?? patientId),
    patient_name: (raw.patient_name as string) ?? patientName,
    domain: String(raw.domain ?? "health"),
    type: String(raw.type ?? "task"),
    description: String(raw.description ?? "—"),
    urgency_level: String(raw.urgency_level ?? "medium"),
    review_by: (raw.review_by as string | null) ?? null,
    is_overdue: Number(raw.is_overdue ?? 0),
    completed: Number(raw.completed ?? 0),
    draft_content: (raw.draft_content as string | null) ?? null,
    modification_in_progress: raw.modification_in_progress as number | undefined,
    idempotency_key: raw.idempotency_key as string | null | undefined,
    manual_action_type: (raw.manual_action_type as string | null) ?? null,
    scheduling_status: (raw.scheduling_status as string | null) ?? null,
    assigned_caregiver: (raw.assigned_caregiver as string | null) ?? null,
    created_at: raw.created_at as string | undefined,
    recipient_email: (raw.recipient_email as string | null) ?? null,
    recipient_type: (raw.recipient_type as string | null) ?? null,
    email_subject: (raw.email_subject as string | null) ?? null,
    api_payload: (raw.api_payload as Record<string, unknown> | null) ?? null,
    execution_plan: raw.execution_plan as ExecutionPlan | undefined,
    outcome: (raw.outcome as string | null) ?? null,
    completion_date: (raw.completion_date as string | null) ?? null,
  };
}

export function resolvePendingAction(
  p: Record<string, unknown>,
  feed: Action[],
  patientId: string,
  patientName: string
): Action | null {
  if (p == null || typeof p !== "object") return null;
  const id = p.action_id != null ? String(p.action_id) : "";
  if (!id) return null;
  const fromFeed = feed.find((a) => a.action_id === id);
  if (fromFeed) return fromFeed;
  return coalesceRecordToAction(p, patientId, patientName);
}

function emptyDomainBuckets() {
  return { pending: [] as Action[], completed: [] as Action[], dismissed: [] as Action[] };
}

export type DomainBuckets = {
  pending: Action[];
  completed: Action[];
  dismissed: Action[];
};

export function groupPatientOverviewActions(
  pendingRaw: Record<string, unknown>[],
  historyRaw: Record<string, unknown>[],
  feed: Action[],
  patientId: string,
  patientName: string
): Record<DomainKey, DomainBuckets> {
  const out: Record<DomainKey, DomainBuckets> = {
    health: emptyDomainBuckets(),
    grocery: emptyDomainBuckets(),
    financial: emptyDomainBuckets(),
    appointment: emptyDomainBuckets(),
  };

  for (const raw of pendingRaw) {
    const a = resolvePendingAction(raw, feed, patientId, patientName);
    if (!a) continue;
    out[normalizeDomain(a.domain)].pending.push(a);
  }

  for (const raw of historyRaw) {
    const a = coalesceRecordToAction(raw, patientId, patientName);
    const d = normalizeDomain(a.domain);
    const oc = a.outcome ? String(a.outcome).toLowerCase() : "";
    if (oc === "dismissed") {
      out[d].dismissed.push(a);
    } else {
      out[d].completed.push(a);
    }
  }

  return out;
}

const PREVIEW_LEN = 120;

export function actionPreviewText(action: Action): string {
  const draft = action.draft_content?.trim();
  if (draft) {
    return draft.length > PREVIEW_LEN ? `${draft.slice(0, PREVIEW_LEN)}…` : draft;
  }
  return action.description;
}
