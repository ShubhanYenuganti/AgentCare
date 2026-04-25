import { useApi } from "../hooks/useApi";

interface Patient {
  patient_id: string;
  name: string;
  age: number | null;
  address: string | null;
  active: number;
  preferences_json: Record<string, unknown>;
  life_graph_json: Record<string, unknown>;
}

export default function Patients() {
  const { data, loading, error } = useApi<Patient[]>("/patients");

  if (loading) {
    return (
      <main style={{ padding: "1.5rem", fontFamily: "system-ui, sans-serif" }}>
        <p>Loading patients…</p>
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
        <h1 style={{ marginBottom: "0.5rem" }}>Patient Roster</h1>
        <p>No patients found.</p>
      </main>
    );
  }

  return (
    <main style={{ padding: "1.5rem", fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ marginBottom: "1rem" }}>Patient Roster</h1>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {data.map((patient) => (
          <li
            key={patient.patient_id}
            style={{
              padding: "0.75rem 1rem",
              marginBottom: "0.5rem",
              border: "1px solid #ddd",
              borderRadius: "6px",
              display: "flex",
              gap: "1.5rem",
              alignItems: "center",
            }}
          >
            <span style={{ fontWeight: 600, minWidth: "160px" }}>{patient.name}</span>
            <span style={{ color: "#555" }}>Age: {patient.age ?? "—"}</span>
            <span style={{ color: "#555", flex: 1 }}>{patient.address ?? "No address"}</span>
            <span
              style={{
                padding: "2px 8px",
                borderRadius: "9999px",
                fontSize: "0.75rem",
                fontWeight: 600,
                backgroundColor: patient.active ? "#D1FAE5" : "#FEE2E2",
                color: patient.active ? "#065F46" : "#991B1B",
              }}
            >
              {patient.active ? "Active" : "Inactive"}
            </span>
          </li>
        ))}
      </ul>
    </main>
  );
}
