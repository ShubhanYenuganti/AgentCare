import { Link, Navigate, Route, Routes } from "react-router-dom";
import Actions from "./pages/Actions";
import Patients from "./pages/Patients";
import Caregivers from "./pages/Caregivers";
import Org from "./pages/Org";

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
        <Route path="/actions" element={<Actions />} />
        <Route path="/patients" element={<Patients />} />
        <Route path="/caregivers" element={<Caregivers />} />
        <Route path="/org" element={<Org />} />
      </Routes>
    </div>
  );
}
