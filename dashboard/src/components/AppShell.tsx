import { useEffect, type CSSProperties } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useGetSetupStatusQuery } from "../api/client";

const NAV_LINKS = [
  { to: "/actions", label: "Action Feed" },
  { to: "/patients", label: "Patients" },
  { to: "/caregivers", label: "Caregivers" },
  { to: "/org", label: "Org" },
  { to: "/chat", label: "Chat" },
];

const TOP_BAR_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  height: "56px",
  padding: "0 1.25rem",
  background: "#e8eaed",
  borderBottom: "1px solid #d1d5db",
  gap: "1.25rem",
  boxSizing: "border-box",
};

const BRAND_STYLE: CSSProperties = {
  fontWeight: 500,
  fontSize: "1.05rem",
  letterSpacing: "0.04em",
  color: "#0a0a0a",
  marginRight: "0.5rem",
};

const NAV_ROW: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.35rem",
  flexWrap: "wrap",
};

const navLinkBase: CSSProperties = {
  textDecoration: "none",
  padding: "0.45rem 1rem",
  borderRadius: "9999px",
  fontSize: "0.9rem",
  fontWeight: 400,
  border: "1px solid transparent",
  color: "rgba(10, 10, 10, 0.72)",
};

export default function AppShell() {
  const navigate = useNavigate();
  const { data: setupStatus, isLoading } = useGetSetupStatusQuery();

  useEffect(() => {
    if (!isLoading && setupStatus && !setupStatus.org_configured) {
      navigate("/onboarding", { replace: true });
    }
  }, [isLoading, setupStatus, navigate]);

  if (isLoading) {
    return <div style={{ minHeight: "100vh", background: "#e8eaed" }} />;
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: "100vh",
        background: "#e8eaed",
      }}
    >
      <header style={TOP_BAR_STYLE}>
        <span style={BRAND_STYLE}>AgentCare</span>
        <nav style={NAV_ROW}>
          {NAV_LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              style={({ isActive }) => ({
                ...navLinkBase,
                color: isActive ? "#0a0a0a" : "rgba(10, 10, 10, 0.48)",
                fontWeight: isActive ? 500 : 400,
                background: isActive ? "rgba(255, 255, 255, 0.98)" : "transparent",
                border: isActive ? "1px solid rgba(0, 0, 0, 0.05)" : "1px solid transparent",
                boxShadow: isActive ? "0 2px 8px rgba(0, 0, 0, 0.06), inset 0 1px 0 rgba(255, 255, 255, 0.95)" : "none",
              })}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main style={{ flex: 1, overflow: "auto", width: "100%", minHeight: 0, background: "#e8eaed" }}>
        <Outlet />
      </main>
    </div>
  );
}
