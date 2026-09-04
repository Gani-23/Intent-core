import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";

import ProtectedRoute from "./components/ProtectedRoute";
import { AuthProvider } from "./lib/auth";
import { ApiConfigProvider } from "./lib/api";
import { useLenisScroll } from "./hooks/useLenisScroll";

const HomePage = lazy(() => import("./pages/HomePage"));
const CommandCenterPage = lazy(() => import("./pages/CommandCenterPage"));
const RuntimeReviewsPage = lazy(() => import("./pages/RuntimeReviewsPage"));
const DeploymentDebtPage = lazy(() => import("./pages/DeploymentDebtPage"));
const IncidentsPage = lazy(() => import("./pages/IncidentsPage"));
const OnboardingPage = lazy(() => import("./pages/OnboardingPage"));
const LaunchGuidePage = lazy(() => import("./pages/LaunchGuidePage"));
const ProofBundlesPage = lazy(() => import("./pages/ProofBundlesPage"));
const TargetsPage = lazy(() => import("./pages/TargetsPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const AdminAccessPage = lazy(() => import("./pages/AdminAccessPage"));
const AdminWorkspacePage = lazy(() => import("./pages/AdminWorkspacePage"));
const AdminSecretsPage = lazy(() => import("./pages/AdminSecretsPage"));
const SessionEventsPage = lazy(() => import("./pages/SessionEventsPage"));
const IncidentReplayPage = lazy(() => import("./pages/IncidentReplayPage"));
const WouldItCatchPage = lazy(() => import("./pages/WouldItCatchPage"));

export default function App() {
  useLenisScroll();

  return (
    <AuthProvider>
      <ApiConfigProvider>
        <Suspense fallback={<div className="route-loading">Loading signal surface...</div>}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/onboarding" element={<OnboardingPage />} />
            <Route path="/launch-guide" element={<LaunchGuidePage />} />
            <Route
              path="/proof-bundles"
              element={
                <ProtectedRoute permission="reports">
                  <ProofBundlesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/targets"
              element={
                <ProtectedRoute permission="targets">
                  <TargetsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/command"
              element={
                <ProtectedRoute permission="reports">
                  <CommandCenterPage />
                </ProtectedRoute>
              }
            />
            <Route path="/sessions/events" element={<SessionEventsPage />} />
            <Route path="/sessions/replay" element={<IncidentReplayPage />} />
            <Route path="/audit/would-it-catch" element={<WouldItCatchPage />} />
            <Route
              path="/command/reviews"
              element={
                <ProtectedRoute permission="reviews">
                  <RuntimeReviewsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/command/deployment-debt"
              element={
                <ProtectedRoute permission="reports">
                  <DeploymentDebtPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/command/incidents"
              element={
                <ProtectedRoute permission="reports">
                  <IncidentsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/access"
              element={
                <ProtectedRoute permission="admin">
                  <AdminAccessPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/workspace"
              element={
                <ProtectedRoute permission="workspace">
                  <AdminWorkspacePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/secrets"
              element={
                <ProtectedRoute permission="admin">
                  <AdminSecretsPage />
                </ProtectedRoute>
              }
            />
          </Routes>
        </Suspense>
      </ApiConfigProvider>
    </AuthProvider>
  );
}
