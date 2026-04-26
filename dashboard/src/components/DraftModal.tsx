import { useState } from "react";
import { usePatchActionMutation } from "../api/client";
import type { Action } from "../types";

interface Props {
  action: Action;
  onClose: () => void;
  onSubmitted: () => void;
}

function generateKey(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function DraftModal({ action, onClose, onSubmitted }: Props) {
  const [instruction, setInstruction] = useState("");
  const [patchAction] = usePatchActionMutation();

  const handleSubmit = () => {
    if (!instruction.trim()) return;
    patchAction({
      id: action.action_id,
      body: {
        modification_instruction: instruction.trim(),
        idempotency_key: generateKey(),
      },
    });
    onSubmitted();
  };

  return (
    <>
      <div
        onClick={onClose}
        style={{ position: "fixed", inset: 0, backgroundColor: "rgba(0,0,0,0.4)", zIndex: 60 }}
      />
      <div
        style={{
          position: "fixed",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: "560px",
          maxWidth: "95vw",
          backgroundColor: "#fff",
          borderRadius: "8px",
          boxShadow: "0 20px 60px rgba(0,0,0,0.2)",
          zIndex: 70,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div style={{ padding: "1.25rem 1.5rem", borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>Modify Draft</h2>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1.25rem", color: "#6b7280" }}>×</button>
        </div>

        <div style={{ padding: "1.25rem 1.5rem" }}>
          <p style={{ fontSize: "0.8rem", color: "#6b7280", margin: "0 0 0.5rem" }}>Current draft</p>
          <div
            style={{
              padding: "0.75rem",
              backgroundColor: "#f9fafb",
              border: "1px solid #e5e7eb",
              borderRadius: "6px",
              fontSize: "0.875rem",
              lineHeight: "1.6",
              color: "#374151",
              maxHeight: "200px",
              overflowY: "auto",
              whiteSpace: "pre-wrap",
              marginBottom: "1rem",
            }}
          >
            {action.draft_content || "(No draft content)"}
          </div>

          <label style={{ fontSize: "0.875rem", fontWeight: 500, color: "#374151", display: "block", marginBottom: "0.5rem" }}>
            Modification instruction
          </label>
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="Describe what to change in the draft…"
            rows={4}
            style={{
              width: "100%",
              resize: "vertical",
              border: "1px solid #d1d5db",
              borderRadius: "6px",
              padding: "0.5rem",
              fontSize: "0.875rem",
              fontFamily: "inherit",
              boxSizing: "border-box",
            }}
          />
        </div>

        <div style={{ padding: "1rem 1.5rem", borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
          <button
            onClick={onClose}
            style={{ padding: "0.5rem 1rem", border: "1px solid #d1d5db", borderRadius: "6px", background: "#fff", cursor: "pointer", fontSize: "0.875rem" }}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!instruction.trim()}
            style={{
              padding: "0.5rem 1.25rem",
              backgroundColor: "#3b82f6",
              color: "#fff",
              border: "none",
              borderRadius: "6px",
              cursor: !instruction.trim() ? "not-allowed" : "pointer",
              opacity: !instruction.trim() ? 0.6 : 1,
              fontSize: "0.875rem",
              fontWeight: 500,
            }}
          >
            Submit
          </button>
        </div>
      </div>
    </>
  );
}
