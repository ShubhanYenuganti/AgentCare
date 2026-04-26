import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { useGetChatHistoryQuery, useSendChatMessageMutation } from "../api/client";
import type { Action, ChatMessage } from "../types";

const PANEL_W = 360;
const GUTTER = 20;
const Z_BACKDROP = 90;
const Z_PANEL = 100;

/** Aligned with AppShell / Action Feed light surfaces */
const PAGE_BG = "#e8eaed";
const PANEL = "#ffffff";
const BAR = "#f0f2f5";
const MESSAGE_BG = "#f3f4f6";
const TEXT = "#0a0a0a";
const TEXT_MUTED = "#4b5563";
const TEXT_SOFT = "#6b7280";
const PLACEHOLDER = "#9ca3af";
const BORDER = "#e5e7eb";
const BORDER_STR = "#d1d5db";
const ACCENT = "#3b82f6";
const SHADOW = "0 20px 48px rgba(15, 23, 42, 0.08), 0 0 0 1px #e5e7eb";

/** Match ActionCard `section` + `mono` (Action draft box) */
const DRAFT_BOX_BG = "rgba(255, 255, 255, 0.75)";
const DRAFT_BOX_BORDER = "#e5e7eb";
const DRAFT_TEXT = "#1f2937";
const DRAFT_PLACEHOLDER = "#6b7280";
const DRAFT_FONT =
  "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace";
const DRAFT_SIZE = "0.75rem";

interface Props {
  action: Action;
  onClose: () => void;
}

function isAssistant(m: ChatMessage) {
  return m.role === "assistant" || (m as { role: string }).role === "agent";
}

function ArrowUp({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 19V5M5 12l7-7 7 7"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ThinkingRow() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.4rem",
        fontSize: "0.8rem",
        color: TEXT_SOFT,
        fontWeight: 500,
        padding: "0.35rem 0",
      }}
      aria-live="polite"
      aria-busy
    >
      <span style={{ display: "inline-flex", gap: 3, alignItems: "center" }}>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              background: "#94a3b8",
              animation: "acp-dot 1.2s ease-in-out infinite",
              animationDelay: `${i * 0.2}s`,
            }}
          />
        ))}
      </span>
      <span>Thinking about your question…</span>
      <style>{`@keyframes acp-dot{0%,80%,100%{opacity:.35;transform:scale(.85)}40%{opacity:1;transform:scale(1)}}`}</style>
    </div>
  );
}

function DragHandle({ onPointerDown }: { onPointerDown: (e: React.PointerEvent) => void }) {
  return (
    <div
      onPointerDown={onPointerDown}
      style={{
        flex: 1,
        minWidth: 0,
        cursor: "grab",
        padding: "6px 2px 6px 4px",
        userSelect: "none",
        touchAction: "none" as const,
        display: "flex",
        alignItems: "center",
        borderRadius: 6,
        color: PLACEHOLDER,
      }}
      aria-label="Move chat"
      title="Drag to move"
    >
      <span style={{ fontSize: "1rem", letterSpacing: 2, lineHeight: 1 }}>⋮⋮</span>
    </div>
  );
}

export default function ActionChatPanel({ action, onClose }: Props) {
  const actionId = action.action_id;
  const [input, setInput] = useState("");
  const [awaitingReply, setAwaitingReply] = useState(false);
  const [pos, setPos] = useState(() => {
    if (typeof window === "undefined") return { left: 100, top: 100 };
    return {
      left: Math.max(GUTTER, window.innerWidth - PANEL_W - GUTTER),
      top: Math.max(GUTTER, (window.innerHeight - 360) / 2),
    };
  });
  const assistantCountWhenSent = useRef(0);
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const posRef = useRef(pos);
  posRef.current = pos;

  const { data: messages = [] } = useGetChatHistoryQuery(actionId, {
    pollingInterval: 3000,
  });
  const [sendMessage, { isLoading: sending }] = useSendChatMessageMutation();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const assistantThread = messages.filter((m) => isAssistant(m));

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, assistantThread, awaitingReply, sending]);

  useEffect(() => {
    if (!awaitingReply) return;
    const n = messages.filter((m) => isAssistant(m)).length;
    if (n > assistantCountWhenSent.current) {
      setAwaitingReply(false);
    }
  }, [messages, awaitingReply]);

  const showThinking = sending || (awaitingReply && !sending);
  const showComposer = !showThinking;

  useEffect(() => {
    if (!showComposer) return;
    const id = requestAnimationFrame(() => areaRef.current?.focus());
    return () => cancelAnimationFrame(id);
  }, [showComposer]);

  const onDragBarPointerDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    e.preventDefault();
    const startX = e.clientX;
    const startY = e.clientY;
    const origL = posRef.current.left;
    const origT = posRef.current.top;
    const w = PANEL_W;

    const onMove = (ev: PointerEvent) => {
      const h = panelRef.current?.getBoundingClientRect().height ?? 400;
      const newL = origL + (ev.clientX - startX);
      const newT = origT + (ev.clientY - startY);
      setPos({
        left: Math.max(8, Math.min(newL, window.innerWidth - w - 8)),
        top: Math.max(8, Math.min(newT, window.innerHeight - h - 8)),
      });
    };
    const onUp = () => {
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
      document.removeEventListener("pointercancel", onUp);
    };
    document.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("pointerup", onUp);
    document.addEventListener("pointercancel", onUp);
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    assistantCountWhenSent.current = messages.filter((m) => isAssistant(m)).length;
    setAwaitingReply(true);
    try {
      await sendMessage({ actionId, message: text }).unwrap();
    } catch {
      setAwaitingReply(false);
    }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  const hasBody = showThinking || assistantThread.length > 0;

  const taId = `acp-ta-${actionId.replace(/[^a-zA-Z0-9_-]/g, "_")}`;

  const content = (
    <>
      <style>{`#${taId}::placeholder { color: ${DRAFT_PLACEHOLDER}; opacity: 1; }`}</style>
      <div
        role="presentation"
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          zIndex: Z_BACKDROP,
          background: "rgba(15, 23, 42, 0.1)",
        }}
        aria-hidden
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal
        aria-label="Action chat"
        onClick={(e) => e.stopPropagation()}
        style={{
          position: "fixed",
          zIndex: Z_PANEL,
          left: pos.left,
          top: pos.top,
          width: PANEL_W,
          maxWidth: `min(${PANEL_W}px, calc(100vw - 16px))`,
          maxHeight: "min(85vh, 560px)",
          boxSizing: "border-box",
          display: "flex",
          flexDirection: "column",
          background: PANEL,
          borderRadius: 20,
          boxShadow: SHADOW,
          color: TEXT,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            gap: 4,
            padding: "0.35rem 0.4rem 0.35rem 0.5rem",
            borderBottom: `1px solid ${BORDER}`,
            background: BAR,
          }}
        >
          <DragHandle onPointerDown={onDragBarPointerDown} />
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onClose();
            }}
            style={{
              flexShrink: 0,
              width: 28,
              height: 28,
              border: `1px solid ${BORDER}`,
              borderRadius: 8,
              background: PANEL,
              color: TEXT_MUTED,
              cursor: "pointer",
              fontSize: "1.1rem",
              lineHeight: 1,
            }}
            aria-label="Close ask"
          >
            ×
          </button>
        </div>

        {hasBody && (
          <div
            style={{
              flex: assistantThread.length > 0 ? 1 : undefined,
              minHeight: 0,
              maxHeight: showThinking && !assistantThread.length ? 120 : undefined,
              overflowY: assistantThread.length > 0 ? "auto" : "visible",
              padding: "0.5rem 0.75rem 0.4rem",
              display: "flex",
              flexDirection: "column",
              gap: 8,
              background: PAGE_BG,
            }}
          >
            {assistantThread.map((msg, i) => (
              <div
                key={`${String((msg as ChatMessage & { id?: string }).message_id ?? i)}-asst`}
                style={{
                  alignSelf: "flex-start",
                  maxWidth: "100%",
                  padding: "0.5rem 0.7rem",
                  borderRadius: 12,
                  background: MESSAGE_BG,
                  color: TEXT,
                  border: `1px solid ${BORDER}`,
                  fontSize: "0.8rem",
                  lineHeight: 1.5,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {msg.content}
              </div>
            ))}
            {showThinking && (
              <div
                style={{
                  alignSelf: "stretch",
                  borderTop: assistantThread.length > 0 ? `1px solid ${BORDER}` : "none",
                  paddingTop: assistantThread.length > 0 ? "0.5rem" : 0,
                }}
              >
                <ThinkingRow />
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}

        {showComposer && (
          <div
            style={{
              flexShrink: 0,
              display: "flex",
              gap: "0.4rem",
              alignItems: "flex-end",
              padding: hasBody ? "0.5rem 0.65rem 0.65rem" : "0.6rem 0.65rem 0.65rem",
              borderTop: hasBody ? `1px solid ${BORDER}` : "none",
              background: PAGE_BG,
            }}
          >
            <textarea
              id={taId}
              ref={areaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Ask a question about this action…"
              rows={3}
              style={{
                flex: 1,
                height: 80,
                minHeight: 80,
                maxHeight: 80,
                resize: "none",
                border: `1px solid ${DRAFT_BOX_BORDER}`,
                borderRadius: 12,
                padding: "0.5rem 0.65rem",
                background: DRAFT_BOX_BG,
                color: DRAFT_TEXT,
                fontSize: DRAFT_SIZE,
                lineHeight: 1.5,
                fontFamily: DRAFT_FONT,
                outline: "none",
                boxSizing: "border-box" as const,
                overflow: "auto",
              }}
              disabled={sending}
            />
            <button
              type="button"
              onClick={() => void handleSend()}
              disabled={sending || !input.trim()}
              style={{
                flexShrink: 0,
                width: 32,
                height: 32,
                border: "none",
                borderRadius: "50%",
                background:
                  !input.trim() || sending
                    ? "#e5e7eb"
                    : ACCENT,
                color: !input.trim() || sending ? PLACEHOLDER : "#ffffff",
                cursor: !input.trim() || sending ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: 0,
                boxShadow: !input.trim() || sending ? "none" : "0 1px 2px rgba(0,0,0,0.06)",
              }}
              aria-label="Send message"
              title="Send"
            >
              <ArrowUp size={14} />
            </button>
          </div>
        )}
      </div>
    </>
  );

  if (typeof document === "undefined") {
    return null;
  }
  return createPortal(content, document.body);
}
