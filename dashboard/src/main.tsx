import "./index.css";
import React, { lazy, Suspense } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Provider } from "react-redux";
import { store } from "./api/client";
import AppShell from "./components/AppShell";

const ActionFeed = lazy(() => import("./views/ActionFeed"));
const PatientRoster = lazy(() => import("./views/PatientRoster"));
const CaregiverManagement = lazy(() => import("./views/CaregiverManagement"));
const OrgDashboard = lazy(() => import("./views/OrgDashboard"));
const Onboarding = lazy(() => import("./views/Onboarding"));
const ChatPanel = lazy(() => import("./components/ChatPanel"));

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Provider store={store}>
      <BrowserRouter>
        <Routes>
          <Route
            path="/onboarding"
            element={
              <Suspense fallback={<div style={{ minHeight: "100vh", background: "#f3f4f6" }} />}>
                <Onboarding />
              </Suspense>
            }
          />
          <Route element={<AppShell />}>
            <Route path="/" element={<Navigate to="/actions" replace />} />
            <Route
              path="/actions"
              element={
                <Suspense fallback={<p style={{ padding: "1.5rem" }}>Loading…</p>}>
                  <ActionFeed />
                </Suspense>
              }
            />
            <Route
              path="/patients"
              element={
                <Suspense fallback={<p style={{ padding: "1.5rem" }}>Loading…</p>}>
                  <PatientRoster />
                </Suspense>
              }
            />
            <Route
              path="/caregivers"
              element={
                <Suspense fallback={<p style={{ padding: "1.5rem" }}>Loading…</p>}>
                  <CaregiverManagement />
                </Suspense>
              }
            />
            <Route
              path="/org"
              element={
                <Suspense fallback={<p style={{ padding: "1.5rem" }}>Loading…</p>}>
                  <OrgDashboard />
                </Suspense>
              }
            />
            <Route
              path="/chat"
              element={
                <Suspense fallback={<p style={{ padding: "1.5rem" }}>Loading…</p>}>
                  <ChatPanel />
                </Suspense>
              }
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </Provider>
  </React.StrictMode>
);
