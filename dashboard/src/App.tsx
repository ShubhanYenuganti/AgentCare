import { Link, Navigate, Route, Routes } from "react-router-dom";

function Placeholder({ title }: { title: string }) {
  return (
    <main style={{ padding: "1.5rem", fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ marginBottom: "0.5rem" }}>{title}</h1>
      <p>Scaffold placeholder for Sprint 1.</p>
    </main>
  );
}

export default function App() {
  return (
    <div>
      <nav style={{ display: "flex", gap: "1rem", padding: "1rem", borderBottom: "1px solid #ddd" }}>
        <Link to="/actions">Action Feed</Link>
        <Link to="/patients">Patients</Link>
        <Link to="/caregivers">Caregivers</Link>
        <Link to="/org">Org</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Navigate to="/actions" replace />} />
        <Route path="/actions" element={<Placeholder title="Action Feed" />} />
        <Route path="/patients" element={<Placeholder title="Patient Roster" />} />
        <Route path="/caregivers" element={<Placeholder title="Caregiver Management" />} />
        <Route path="/org" element={<Placeholder title="Organisation Dashboard" />} />
      </Routes>
    </div>
  );
}
