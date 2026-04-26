/**
 * Human-readable urgency for action / patient tier fields.
 * tier_0: overdue/escalated in backend; shown as most severe.
 */
const URGENCY_DISPLAY: Record<string, string> = {
  tier_0: "Critical",
  tier_1: "Urgent",
  tier_2: "Soon",
  tier_3: "Routine",
  high: "Urgent",
  medium: "Soon",
  low: "Routine",
};

export function urgencyDisplayLabel(level: string | null | undefined): string {
  if (level == null || level === "") return "—";
  return URGENCY_DISPLAY[level] ?? level;
}
