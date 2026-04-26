import type { ExecutionPlanStep } from "../types";

/**
 * Human-readable copy for each automation step. Keys are canonical: "METHOD /path…"
 * (matches execution_plan steps from the API).
 */
const VERBOSE_BY_ROUTE: Record<string, string> = {
  "POST /mock/cvs/refill": "Request a prescription refill at the patient’s pharmacy and coordinate pickup or delivery.",
  "GET /mock/cvs/available": "Check which medications are available to refill at the patient’s pharmacy before moving forward.",
  "GET /mock/cal/available": "Look up open time slots on the provider’s calendar before booking a visit.",
  "POST /mock/cal/book": "Book a clinic or telehealth appointment with the chosen provider and preferred times.",
  "POST /mock/instacart/cart": "Build a grocery delivery cart with the items needed for the patient (instacart-style flow).",
  "POST /mock/amazon/order": "Place a household or medical supply order for delivery to the patient.",
  "POST /mock/amazon/reorder": "Place a repeat / one-click reorder of supplies the patient has ordered before.",
  "POST /mock/caregivers/available": "Look up which caregivers are free on the requested date and duration so a visit or assignment can be scheduled.",
  "GET gmaps:/maps/api/distancematrix/json": "Get travel times between locations to help plan realistic visit and transport windows.",
  "POST resend:/emails": "Send the prepared email to the intended recipient through the email delivery system.",
};

/** Build one display key so we never show "POST POST /path" when `route` already includes the method. */
export function canonicalAutomationRoute(s: ExecutionPlanStep): string {
  const raw = (s.route ?? "").trim();
  if (/^(GET|POST|PUT|PATCH|DELETE)\s/i.test(raw)) {
    return normalizeMethodPrefix(raw);
  }
  const m = (s.method ?? "GET").trim().toUpperCase();
  return `${m} ${raw}`.replace(/\s+/g, " ").trim();
}

function normalizeMethodPrefix(line: string): string {
  const t = line.trim();
  const m = t.match(/^(get|post|put|patch|delete)\s+(.+)$/i);
  if (m) return `${m[1].toUpperCase()} ${m[2]}`;
  return t;
}

/** Short, user-facing line for a planned automation step. Falls back to the canonical route if unknown. */
export function formatAutomationStepTitle(s: ExecutionPlanStep): string {
  const key = canonicalAutomationRoute(s);
  return VERBOSE_BY_ROUTE[key] ?? key;
}
