import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { useGetActionsQuery } from "../api/client";
import ActionCard from "../components/ActionCard";
import { useLocation, useSearchParams } from "react-router-dom";

/** Full-bleed background; main column is left-aligned (avoids clashing with side modals e.g. Ask). */
const PAGE_SHEET: CSSProperties = {
  minHeight: "calc(100vh - 56px)",
  width: "100%",
  background: "#e8eaed",
  boxSizing: "border-box",
};

const PAGE_INNER: CSSProperties = {
  maxWidth: "min(1280px, 100%)",
  width: "100%",
  margin: 0,
  padding: "1.5rem clamp(1rem, 4vw, 2.5rem) 2.5rem",
  boxSizing: "border-box",
};

const TITLE_BLOCK: CSSProperties = {
  marginBottom: "1.5rem",
  textAlign: "left",
};

const H1: CSSProperties = {
  margin: 0,
  fontSize: "1.75rem",
  fontWeight: 600,
  letterSpacing: "-0.02em",
  color: "#0a0a0a",
};

const SUB: CSSProperties = {
  display: "block",
  marginTop: "0.35rem",
  fontSize: "0.9rem",
  fontWeight: 500,
  color: "#374151",
};

const LIST: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
};

const ERR_COLOR: CSSProperties = { color: "#b91c1c" };
const MUTED: CSSProperties = { color: "#4b5563" };

export default function ActionFeed() {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const fromQuery = searchParams.get("action");
  const fromState = (location.state as { highlightActionId?: string } | null)?.highlightActionId;
  const focusId = fromState || fromQuery || undefined;
  const scrolledFor = useRef<string | null>(null);
  const [showFocusRing, setShowFocusRing] = useState(true);

  useEffect(() => {
    setShowFocusRing(true);
  }, [focusId]);

  useEffect(() => {
    if (!focusId || !showFocusRing) return;
    const onDown = (e: MouseEvent) => {
      const el = document.getElementById(`action-focus-${focusId}`);
      if (el && el.contains(e.target as Node)) return;
      setShowFocusRing(false);
    };
    document.addEventListener("mousedown", onDown, true);
    return () => document.removeEventListener("mousedown", onDown, true);
  }, [focusId, showFocusRing]);

  const { data: actions = [], isLoading, error } = useGetActionsQuery(
    { sort: "rank" },
    { pollingInterval: 10000 }
  );

  useLayoutEffect(() => {
    if (!focusId) {
      scrolledFor.current = null;
      return;
    }
    if (isLoading) return;
    if (!actions.some((a) => a.action_id === focusId)) return;
    if (scrolledFor.current === focusId) return;
    requestAnimationFrame(() => {
      const el = document.getElementById(`action-focus-${focusId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        scrolledFor.current = focusId;
      }
    });
  }, [focusId, isLoading, actions]);

  if (isLoading) {
    return (
      <div style={PAGE_SHEET}>
        <div style={PAGE_INNER}>
          <p style={{ margin: 0, color: "#374151" }}>Loading actions…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={PAGE_SHEET}>
        <div style={PAGE_INNER}>
          <p style={{ margin: 0, ...ERR_COLOR }}>Failed to load actions.</p>
        </div>
      </div>
    );
  }

  const pendingCount = actions.filter((a) => a.completed === 0).length;
  const completedAutonomousCount = actions.filter(
    (a) =>
      a.completed === 1 &&
      !String(a.manual_action_type ?? "").trim() &&
      a.outcome === "approved"
  ).length;

  return (
    <div style={PAGE_SHEET}>
      <div style={PAGE_INNER}>
        <div style={TITLE_BLOCK}>
          <h1 style={H1}>Action Feed</h1>
          <span style={SUB}>
            {pendingCount} pending
            {completedAutonomousCount > 0
              ? ` · ${completedAutonomousCount} completed (automation)`
              : ""}
            {actions.length === 0 ? " — you’re all caught up" : ""}
          </span>
        </div>

        {actions.length === 0 ? (
          <p style={MUTED}>No pending actions.</p>
        ) : (
          <div style={LIST}>
            {actions.map((action) => (
              <ActionCard
                key={action.action_id}
                action={action}
                highlighted={Boolean(
                  focusId && showFocusRing && action.action_id === focusId
                )}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
