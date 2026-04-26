import { useState, type CSSProperties } from "react";
import { useApproveDraftMutation, useDiscardDraftMutation, useModifyDraftMutation } from "../api/client";
import type { StagedActionDraft } from "../types";

interface Props {
  draftId: string;
  draft: StagedActionDraft;
  onApproved: () => void;
  onDiscarded: () => void;
  onModified: (reply: string) => void;
}

const CARD: CSSProperties = {
  background: "#fff",
  border: "1px solid #e5e7eb",
  borderRadius: "12px",
  padding: "1rem 1.25rem",
  maxWidth: "420px",
  boxShadow: "0 1px 4px rgba(0,0,0,0.07)",
};

const ROW: CSSProperties = { display: "flex", gap: "0.5rem", marginTop: "0.85rem", flexWrap: "wrap" };

const BTN: CSSProperties = {
  padding: "0.4rem 0.9rem",
  borderRadius: "8px",
  border: "none",
  cursor: "pointer",
  fontSize: "0.85rem",
  fontWeight: 500,
};

const LABEL: CSSProperties = { fontSize: "0.72rem", color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.04em" };
const VALUE: CSSProperties = { fontSize: "0.92rem", color: "#111827", marginBottom: "0.55rem" };

export default function DraftActionCard({ draftId, draft, onApproved, onDiscarded, onModified }: Props) {
  const [approveDraft, { isLoading: approving }] = useApproveDraftMutation();
  const [discardDraft, { isLoading: discarding }] = useDiscardDraftMutation();
  const [modifyDraft, { isLoading: modifying }] = useModifyDraftMutation();

  const [showFeedback, setShowFeedback] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [settled, setSettled] = useState<"approved" | "discarded" | null>(null);

  if (settled === "approved") return <p style={{ color: "#16a34a", fontSize: "0.9rem", padding: "0.5rem 0" }}>Action added to feed.</p>;
  if (settled === "discarded") return <p style={{ color: "#6b7280", fontSize: "0.9rem", padding: "0.5rem 0" }}>Draft discarded.</p>;

  async function handleApprove() {
    await approveDraft(draftId).unwrap();
    setSettled("approved");
    onApproved();
  }

  async function handleDiscard() {
    await discardDraft(draftId).unwrap();
    setSettled("discarded");
    onDiscarded();
  }

  async function handleModifySubmit() {
    if (!feedback.trim()) return;
    const result = await modifyDraft({ draftId, feedback: feedback.trim() }).unwrap();
    setFeedback("");
    setShowFeedback(false);
    onModified(result.reply);
  }

  return (
    <div style={CARD}>
      <p style={{ ...LABEL, marginBottom: "0.6rem" }}>Draft Action</p>
      {draft.patient_id && (
        <>
          <p style={LABEL}>Patient</p>
          <p style={VALUE}>{draft.patient_id}</p>
        </>
      )}
      {draft.domain && (
        <>
          <p style={LABEL}>Domain</p>
          <p style={VALUE}>{String(draft.domain).charAt(0).toUpperCase() + String(draft.domain).slice(1)}</p>
        </>
      )}
      {draft.type && (
        <>
          <p style={LABEL}>Type</p>
          <p style={VALUE}>{draft.type}</p>
        </>
      )}
      {draft.description && (
        <>
          <p style={LABEL}>Description</p>
          <p style={VALUE}>{draft.description}</p>
        </>
      )}
      {draft.schedule && (
        <>
          <p style={LABEL}>Schedule</p>
          <p style={VALUE}>{JSON.stringify(draft.schedule)}</p>
        </>
      )}

      {showFeedback ? (
        <div style={{ marginTop: "0.85rem" }}>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Describe what to change…"
            rows={3}
            style={{
              width: "100%",
              boxSizing: "border-box",
              border: "1px solid #d1d5db",
              borderRadius: "8px",
              padding: "0.5rem 0.75rem",
              fontSize: "0.9rem",
              resize: "vertical",
            }}
          />
          <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
            <button
              onClick={handleModifySubmit}
              disabled={modifying || !feedback.trim()}
              style={{ ...BTN, background: "#2563eb", color: "#fff", opacity: modifying ? 0.6 : 1 }}
            >
              {modifying ? "Revising…" : "Submit"}
            </button>
            <button onClick={() => setShowFeedback(false)} style={{ ...BTN, background: "#f3f4f6", color: "#374151" }}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div style={ROW}>
          <button onClick={handleApprove} disabled={approving} style={{ ...BTN, background: "#16a34a", color: "#fff", opacity: approving ? 0.6 : 1 }}>
            {approving ? "Approving…" : "Approve"}
          </button>
          <button onClick={() => setShowFeedback(true)} style={{ ...BTN, background: "#f3f4f6", color: "#374151" }}>
            Modify
          </button>
          <button onClick={handleDiscard} disabled={discarding} style={{ ...BTN, background: "#fff", color: "#dc2626", border: "1px solid #fca5a5", opacity: discarding ? 0.6 : 1 }}>
            {discarding ? "Discarding…" : "Discard"}
          </button>
        </div>
      )}
    </div>
  );
}
