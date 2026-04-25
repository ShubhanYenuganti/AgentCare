import { useApi } from "../hooks/useApi";

interface OrgContext {
  org_name?: string;
  care_philosophy?: string;
  escalation_chain?: string;
  escalation_lead?: string;
}

function Field({ label, value }: { label: string; value: string | undefined }) {
  return (
    <div style={{ marginBottom: "1rem" }}>
      <dt style={{ fontWeight: 600, color: "#374151", marginBottom: "0.25rem" }}>{label}</dt>
      <dd style={{ margin: 0, color: "#555" }}>{value ?? "—"}</dd>
    </div>
  );
}

export default function Org() {
  const { data, loading, error } = useApi<OrgContext>("/org");

  if (loading) {
    return (
      <main style={{ padding: "1.5rem", fontFamily: "system-ui, sans-serif" }}>
        <p>Loading org context…</p>
      </main>
    );
  }

  if (error) {
    return (
      <main style={{ padding: "1.5rem", fontFamily: "system-ui, sans-serif" }}>
        <p style={{ color: "#EF4444" }}>Error: {error}</p>
      </main>
    );
  }

  if (!data) {
    return (
      <main style={{ padding: "1.5rem", fontFamily: "system-ui, sans-serif" }}>
        <h1 style={{ marginBottom: "0.5rem" }}>Organisation Dashboard</h1>
        <p>No org data available.</p>
      </main>
    );
  }

  return (
    <main style={{ padding: "1.5rem", fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ marginBottom: "1.25rem" }}>Organisation Dashboard</h1>
      <dl>
        <Field label="Org Name" value={data.org_name} />
        <Field label="Care Philosophy" value={data.care_philosophy} />
        <Field label="Escalation Chain" value={data.escalation_chain} />
        <Field label="Escalation Lead" value={data.escalation_lead} />
      </dl>
    </main>
  );
}
