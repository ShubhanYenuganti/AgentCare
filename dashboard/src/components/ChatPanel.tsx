import { useState, useRef, useEffect, type CSSProperties, type ReactNode } from "react";
import {
  useGetGeneralChatHistoryQuery,
  useSendGeneralChatMessageMutation,
} from "../api/client";
import type { GeneralChatMessage, StagedActionDraft } from "../types";
import DraftActionCard from "./DraftActionCard";

const PAGE_BG = "#e8eaed";
const BORDER_SOFT = "rgba(15, 23, 42, 0.08)";
const ACCENT = "#3b82f6";
const TEXT = "#0f172a";
const TEXT_MUTED = "#64748b";

/** Hide parenthesized backend ids like (fin_9ad329f4_63dd6a) from chat display. */
function sanitizeChatDisplay(raw: string): string {
  return raw
    .replace(/\(\s*[a-z]+_[a-z0-9]{4,}(?:_[a-z0-9]+)*\s*\)/gi, "")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n");
}

/** Renders **bold** segments and preserves paragraph breaks for assistant copy. */
function FormattedAssistantBody({ text }: { text: string }) {
  const clean = sanitizeChatDisplay(text);
  const lines = clean.split("\n");
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {lines.map((line, lineIdx) => {
        if (line.trim() === "") {
          return <div key={lineIdx} style={{ height: "0.4rem" }} aria-hidden />;
        }
        return (
          <p key={lineIdx} style={{ margin: 0 }}>
            <SegmentedBold text={line} />
          </p>
        );
      })}
    </div>
  );
}

function SegmentedBold({ text }: { text: string }): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**") && p.length > 4) {
      return (
        <strong key={i} style={{ fontWeight: 650, color: "#0f172a" }}>
          {p.slice(2, -2)}
        </strong>
      );
    }
    return <span key={i}>{p}</span>;
  });
}

const SESSION_KEY = "macos_chat_session_id";

// Per-session draft payload cache: draftId → payload
// We store draft payloads received from the executor in memory so DraftActionCard can render them.
const draftCache: Record<string, StagedActionDraft> = {};

interface LocalMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  stage?: string;
  intent_class?: string | null;
  domain?: string | null;
  draft_action_id?: string | null;
  draft_payload?: StagedActionDraft;
}

function IntentBadge({ intent, domain }: { intent?: string | null; domain?: string | null }) {
  if (!intent) return null;
  const chip: CSSProperties = {
    fontSize: "0.7rem",
    padding: "0.25rem 0.6rem",
    borderRadius: 9999,
    fontWeight: 600,
    letterSpacing: "0.02em",
  };
  return (
    <div style={{ display: "flex", gap: "0.4rem", marginBottom: "0.45rem", flexWrap: "wrap" }}>
      <span style={{ ...chip, background: "rgba(139, 92, 246, 0.12)", color: "#5b21b6", border: "1px solid rgba(139, 92, 246, 0.2)" }}>{intent}</span>
      {domain && (
        <span style={{ ...chip, background: "rgba(59, 130, 246, 0.1)", color: "#1d4ed8", border: "1px solid rgba(59, 130, 246, 0.2)" }}>{domain}</span>
      )}
    </div>
  );
}

function SendIcon() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M22 2L11 13" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M22 2L15 22 11 13 2 9l20-7z" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function fromServerMessages(msgs: GeneralChatMessage[]): LocalMessage[] {
  return msgs.map((m) => ({
    id: String(m.id),
    role: m.role,
    content: m.content,
    stage: m.stage,
    intent_class: m.intent_class,
    domain: m.domain,
    draft_action_id: m.draft_action_id,
    draft_payload: m.draft_action_id ? draftCache[m.draft_action_id] : undefined,
  }));
}

export default function ChatPanel() {
  const [sessionId, setSessionId] = useState<string | null>(() => localStorage.getItem(SESSION_KEY));
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [input, setInput] = useState("");
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: history } = useGetGeneralChatHistoryQuery(sessionId ?? "", {
    skip: !sessionId,
  });

  const [sendMessage, { isLoading: sending }] = useSendGeneralChatMessageMutation();

  // Load history on mount when sessionId present
  useEffect(() => {
    if (history && !historyLoaded) {
      setMessages(fromServerMessages(history));
      setHistoryLoaded(true);
    }
  }, [history, historyLoaded]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");

    const optimisticId = `opt-${Date.now()}`;
    setMessages((prev) => [...prev, { id: optimisticId, role: "user", content: text }]);

    try {
      const result = await sendMessage({ session_id: sessionId ?? undefined, message: text }).unwrap();

      if (!sessionId) {
        localStorage.setItem(SESSION_KEY, result.session_id);
        setSessionId(result.session_id);
      }

      const agentMsg: LocalMessage = {
        id: `agent-${Date.now()}`,
        role: "agent",
        content: result.reply,
        stage: result.stage,
        intent_class: result.intent_class,
        domain: result.domain,
        draft_action_id: result.draft_action_id ?? null,
      };
      setMessages((prev) => [...prev, agentMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: `err-${Date.now()}`, role: "agent", content: "Something went wrong. Please try again.", stage: "error" },
      ]);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleDraftModified(msgId: string, reply: string, draftId: string) {
    // Append the revised reply as a new agent message; DraftActionCard in the original message auto-fetches latest payload
    const newMsg: LocalMessage = {
      id: `revised-${Date.now()}`,
      role: "agent",
      content: reply,
      stage: "draft_ready",
      draft_action_id: draftId,
    };
    setMessages((prev) => prev.map((m) => (m.id === msgId ? { ...m, draft_action_id: null } : m)).concat(newMsg));
  }

  /** Viewport height minus top bar and outer padding — one continuous sheet, inner thread scrolls. */
  const chatViewportH = "calc(100vh - 56px - 2.75rem)";

  const CONTAINER: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    minHeight: "calc(100vh - 56px)",
    background: PAGE_BG,
    boxSizing: "border-box",
  };

  const OUTER: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    width: "100%",
    maxWidth: "min(1280px, 100%)",
    margin: "0 auto",
    padding: "1.25rem clamp(1rem, 4vw, 2.5rem) 1.5rem",
    boxSizing: "border-box",
  };

  const CHAT_SHEET: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    height: chatViewportH,
    maxHeight: chatViewportH,
    borderRadius: 20,
    border: "1px solid rgba(255, 255, 255, 0.7)",
    background: "rgba(255, 255, 255, 0.58)",
    WebkitBackdropFilter: "blur(20px) saturate(170%)",
    backdropFilter: "blur(20px) saturate(170%)",
    boxShadow: "0 20px 48px -24px rgba(15, 23, 42, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.95)",
    overflow: "hidden",
  };

  const SHEET_HEADER: CSSProperties = {
    flexShrink: 0,
    padding: "1rem 1.25rem 0.9rem",
    borderBottom: `1px solid ${BORDER_SOFT}`,
    background: "linear-gradient(180deg, rgba(255, 255, 255, 0.55) 0%, rgba(245, 247, 250, 0.4) 100%)",
  };

  const THREAD: CSSProperties = {
    flex: 1,
    minHeight: 0,
    overflowY: "auto",
    padding: "1.15rem 1.25rem",
    display: "flex",
    flexDirection: "column",
    gap: "1rem",
  };

  const SHEET_FOOTER: CSSProperties = {
    flexShrink: 0,
    padding: "0.8rem 1.15rem 1rem",
    borderTop: `1px solid ${BORDER_SOFT}`,
    background: "linear-gradient(180deg, rgba(248, 250, 252, 0.65) 0%, rgba(255, 255, 255, 0.5) 100%)",
  };

  const INPUT_ROW: CSSProperties = {
    display: "flex",
    gap: "0.65rem",
    alignItems: "flex-end",
  };

  return (
    <div style={CONTAINER}>
      <div style={OUTER}>
        <div style={CHAT_SHEET}>
          <header style={SHEET_HEADER}>
            <h1
              style={{
                margin: 0,
                fontSize: "1.2rem",
                fontWeight: 650,
                letterSpacing: "-0.02em",
                color: TEXT,
                lineHeight: 1.25,
              }}
            >
              Chat
            </h1>
            <p
              style={{
                margin: "0.3rem 0 0",
                fontSize: "0.8125rem",
                color: TEXT_MUTED,
                lineHeight: 1.45,
              }}
            >
              Ask about patients, care tasks, and open actions. Drafts can appear in-thread when suggested.
            </p>
          </header>

          <div style={THREAD}>
            {messages.length === 0 && (
              <div
                style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  textAlign: "center",
                  padding: "1.5rem 1.25rem 2rem",
                  color: TEXT_MUTED,
                }}
              >
                <p style={{ margin: 0, fontSize: "0.9rem", fontWeight: 600, color: "rgba(15, 23, 42, 0.72)" }}>Start a conversation</p>
                <p style={{ margin: "0.4rem 0 0", fontSize: "0.8rem", lineHeight: 1.55, maxWidth: "22rem" }}>
                  Type below — messages and replies stay in this panel.
                </p>
              </div>
            )}

            {messages.map((msg, i) => {
              const isUser = msg.role === "user";
              const isFirstClarifying =
                msg.stage === "clarifying" &&
                msg.intent_class &&
                messages.slice(0, i).every((m) => m.stage !== "clarifying");

              return (
                <div
                  key={msg.id}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: isUser ? "flex-end" : "flex-start",
                  }}
                >
                  {!isUser && isFirstClarifying && (
                    <IntentBadge intent={msg.intent_class} domain={msg.domain} />
                  )}
                  <div
                    style={{
                      maxWidth: "min(100%, 34rem)",
                      padding: isUser ? "0.7rem 1.05rem" : "0.85rem 1.1rem",
                      borderRadius: isUser ? 22 : 18,
                      background: isUser
                        ? "linear-gradient(180deg, #3b82f6 0%, #2563eb 100%)"
                        : "rgba(255, 255, 255, 0.88)",
                      color: isUser ? "#fff" : TEXT,
                      fontSize: "0.9rem",
                      lineHeight: 1.6,
                      boxShadow: isUser
                        ? "0 4px 14px -2px rgba(37, 99, 235, 0.45), 0 1px 0 rgba(255,255,255,0.2) inset"
                        : "0 1px 3px rgba(15, 23, 42, 0.06), inset 0 1px 0 rgba(255,255,255,0.95)",
                      border: isUser ? "1px solid rgba(255,255,255,0.12)" : `1px solid ${BORDER_SOFT}`,
                      wordBreak: "break-word",
                    }}
                  >
                    {isUser ? (
                      <span style={{ whiteSpace: "pre-wrap" }}>{msg.content}</span>
                    ) : (
                      <FormattedAssistantBody text={msg.content} />
                    )}
                  </div>

                  {!isUser && msg.draft_action_id && (
                    <div style={{ marginTop: "0.55rem", maxWidth: "min(100%, 34rem)", width: "100%" }}>
                      <DraftActionCard
                        draftId={msg.draft_action_id}
                        draft={draftCache[msg.draft_action_id] ?? {}}
                        onApproved={() => {}}
                        onDiscarded={() => {}}
                        onModified={(reply) => handleDraftModified(msg.id, reply, msg.draft_action_id!)}
                      />
                    </div>
                  )}

                  {msg.stage === "error" && !isUser && (
                    <p style={{ fontSize: "0.75rem", color: "#dc2626", marginTop: "0.35rem" }}>Error processing request</p>
                  )}
                </div>
              );
            })}
            <div ref={bottomRef} />
          </div>

          <div style={SHEET_FOOTER}>
            <div style={INPUT_ROW}>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Message AgentCare…"
                rows={1}
                disabled={sending}
                style={{
                  flex: 1,
                  minWidth: 0,
                  resize: "none",
                  border: `1px solid ${BORDER_SOFT}`,
                  borderRadius: 9999,
                  padding: "0.7rem 1.1rem",
                  fontSize: "0.9rem",
                  outline: "none",
                  background: sending ? "rgba(248, 250, 252, 0.95)" : "rgba(255, 255, 255, 0.9)",
                  color: TEXT,
                  lineHeight: 1.5,
                  maxHeight: "120px",
                  overflowY: "auto",
                  fontFamily: "inherit",
                  boxShadow: "inset 0 1px 1px rgba(15, 23, 42, 0.04)",
                }}
              />
              <button
                onClick={handleSend}
                disabled={sending || !input.trim()}
                type="button"
                style={{
                  minWidth: "2.75rem",
                  height: "2.75rem",
                  padding: 0,
                  borderRadius: 9999,
                  border: "none",
                  background: sending || !input.trim() ? "rgba(226, 232, 240, 0.95)" : ACCENT,
                  color: sending || !input.trim() ? TEXT_MUTED : "#fff",
                  cursor: sending || !input.trim() ? "default" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  boxShadow:
                    sending || !input.trim() ? "none" : "0 2px 8px rgba(37, 99, 235, 0.28)",
                }}
                aria-label="Send"
              >
                <SendIcon />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
