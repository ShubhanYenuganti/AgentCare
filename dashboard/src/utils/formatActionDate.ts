/** Normalize a backend timestamp (space-separated or missing Z) to a Date. */
function parseBackendDate(iso: string): Date {
  const s = iso.trim().replace(" ", "T");
  // Already has zone (Z or ±hh:mm) — do not append Z (that would break +00:00)
  if (/Z$/i.test(s) || /[+-]\d{2}:\d{2}$/.test(s) || /[+-]\d{4}$/.test(s)) {
    return new Date(s);
  }
  if (/T/.test(s)) {
    return new Date(`${s}Z`);
  }
  return new Date(s);
}

/** Format a backend timestamp for display in the user's local timezone. */
export function formatLocal(iso: string | null | undefined): string {
  if (iso == null || iso === "") return "—";
  const d = parseBackendDate(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

/** Format ISO review_by for display in the user's local timezone. */
export function formatReviewByLocal(iso: string | null | undefined): string | null {
  if (iso == null || iso === "") return null;
  const d = parseBackendDate(iso);
  if (Number.isNaN(d.getTime())) return null;
  const month = d.toLocaleString(undefined, { month: "long" });
  const day = d.getDate();
  const time = d.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
  return `${month} ${day} · ${time}`;
}
