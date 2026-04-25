import { useApi } from "../hooks/useApi";

interface CaregiverAssignment {
  patient_id: string;
  name: string;
  pending_actions: number;
}

interface Caregiver {
  caregiver_id: string;
  name: string;
  availability_today: boolean;
  booked_today: boolean;
  assignments?: CaregiverAssignment[];
}

export default function Caregivers() {
  const { data, loading, error } = useApi<Caregiver[]>("/caregivers");

  if (loading) {
    return (
      <main style={{ padding: "1.5rem", fontFamily: "system-ui, sans-serif" }}>
        <p>Loading caregivers…</p>
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
        <h1 style={{ marginBottom: "0.5rem" }}>Caregiver Management</h1>
        <p>No caregivers found.</p>
      </main>
    );
  }

  return (
    <main style={{ padding: "1.5rem", fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ marginBottom: "1rem" }}>Caregiver Management</h1>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {data.map((caregiver) => (
          <li
            key={caregiver.caregiver_id}
            style={{
              padding: "0.75rem 1rem",
              marginBottom: "0.5rem",
              border: "1px solid #ddd",
              borderRadius: "6px",
            }}
          >
            <div style={{ display: "flex", gap: "1.5rem", alignItems: "center" }}>
              <span style={{ fontWeight: 600, minWidth: "160px" }}>{caregiver.name}</span>
              <span style={{ color: "#555", fontSize: "0.85rem" }}>
                ID: {caregiver.caregiver_id}
              </span>
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: "9999px",
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  backgroundColor: caregiver.availability_today ? "#D1FAE5" : "#F3F4F6",
                  color: caregiver.availability_today ? "#065F46" : "#374151",
                }}
              >
                {caregiver.availability_today ? "Available today" : "Unavailable today"}
              </span>
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: "9999px",
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  backgroundColor: caregiver.booked_today ? "#FEF3C7" : "#F3F4F6",
                  color: caregiver.booked_today ? "#92400E" : "#374151",
                }}
              >
                {caregiver.booked_today ? "Booked" : "Not booked"}
              </span>
            </div>
            {caregiver.assignments && caregiver.assignments.length > 0 && (
              <ul style={{ margin: "0.5rem 0 0 1rem", fontSize: "0.85rem", color: "#555" }}>
                {caregiver.assignments.map((a) => (
                  <li key={a.patient_id}>
                    {a.name} — {a.pending_actions} pending action
                    {a.pending_actions !== 1 ? "s" : ""}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </main>
  );
}
