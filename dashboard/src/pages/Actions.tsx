import { useApi } from "../hooks/useApi";

interface Action {
  action_id: string;
  patient_id: string;
  domain: string;
  type: string;
  description: string;
  urgency_level: string;
  review_by: string | null;
  is_overdue: number;
  completed: number;
  draft_content: string | null;
}

const DOMAIN_COLORS: Record<string, string> = {
  health: "#EF4444",
  appointment: "#3B82F6",
  grocery: "#10B981",
  financial: "#F59E0B",
};

function DomainBadge({ domain }: { domain: string }) {
  const color = DOMAIN_COLORS[domain] || "#6B7280";
  return (
    <span
      style={{
        backgroundColor: color,
        color: "#fff",
        padding: "2px 8px",
        borderRadius: "9999px",
        fontSize: "0.75rem",
        fontWeight: 600,
        textTransform: "capitalize",
      }}
    >
      {domain}
    </span>
  );
}

export default function Actions() {
  const { data, loading, error } = useApi<Action[]>("/actions");

  if (loading) {
    return (
      <main style={{ padding: "1.5rem", fontFamily: "system-ui, sans-serif" }}>
        <p>Loading actions…</p>
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

  if (!data || data.length === 0) {
    return (
      <main style={{ padding: "1.5rem", fontFamily: "system-ui, sans-serif" }}>
        <h1 style={{ marginBottom: "0.5rem" }}>Action Feed</h1>
        <p>No pending actions.</p>
      </main>
    );
  }

  return (
    <main style={{ padding: "1.5rem", fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ marginBottom: "1rem" }}>Action Feed</h1>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #ddd", textAlign: "left" }}>
            <th style={{ padding: "8px" }}>Domain</th>
            <th style={{ padding: "8px" }}>Description</th>
            <th style={{ padding: "8px" }}>Urgency</th>
            <th style={{ padding: "8px" }}>Review By</th>
            <th style={{ padding: "8px" }}>Patient</th>
          </tr>
        </thead>
        <tbody>
          {data.map((action) => (
            <tr
              key={action.action_id}
              style={{
                borderBottom: "1px solid #eee",
                backgroundColor: action.is_overdue ? "#FEF2F2" : "transparent",
              }}
            >
              <td style={{ padding: "8px" }}>
                <DomainBadge domain={action.domain} />
              </td>
              <td style={{ padding: "8px" }}>{action.description}</td>
              <td style={{ padding: "8px" }}>{action.urgency_level}</td>
              <td style={{ padding: "8px" }}>{action.review_by ?? "—"}</td>
              <td style={{ padding: "8px" }}>{action.patient_id}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
