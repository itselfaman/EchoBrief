import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './store/authContext.jsx';
import AuthPage from './pages/AuthPage.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import ResultPage from './pages/ResultPage.jsx';
import Layout from './components/Layout/Layout.jsx';

/**
 * Shared loading screen shown while Supabase resolves the initial session.
 * Both ProtectedRoute and PublicRoute must show the SAME spinner during load —
 * returning null from PublicRoute while ProtectedRoute shows a spinner created
 * a visual flash and triggered extra renders that confused the router.
 */
function AuthLoadingScreen() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        gap: '16px',
      }}
    >
      <div className="spinner" style={{ width: 32, height: 32 }} />
      <span style={{ color: 'var(--color-text-secondary)' }}>Loading EchoBrief…</span>
    </div>
  );
}

/**
 * ProtectedRoute — renders children only when authenticated.
 *
 * FIX: Always show the loading screen while isLoading is true.
 * Previously the ProtectedRoute showed a spinner but PublicRoute returned null,
 * meaning on a cold page-load at /dashboard the ProtectedRoute would briefly
 * render its loading spinner, then PublicRoute (null) would fire, creating a
 * layout shift + re-render chain that looked like a redirect loop.
 */
function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) return <AuthLoadingScreen />;
  return isAuthenticated ? children : <Navigate to="/auth" replace />;
}

/**
 * PublicRoute — renders children only when NOT authenticated (e.g. /auth).
 *
 * FIX 1: Show the loading screen instead of returning null during isLoading.
 *         Returning null caused a brief unmount/remount of the auth page which
 *         triggered Supabase's detectSessionInUrl to re-fire and re-evaluate
 *         the route guards a second time.
 *
 * FIX 2: The redirect target is /dashboard, not the catch-all — so we keep
 *         authenticated users in a known good route.
 */
function PublicRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) return <AuthLoadingScreen />;
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : children;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public — unauthenticated only */}
        <Route
          path="/auth"
          element={
            <PublicRoute>
              <AuthPage />
            </PublicRoute>
          }
        />

        {/* Protected — wrapped in shared Layout */}
        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/media/:fileId" element={<ResultPage />} />
        </Route>

        {/*
         * Catch-all: redirect to /auth (not /dashboard).
         *
         * FIX: Previously this redirected to /dashboard, meaning an unauthenticated
         * user on any unknown URL would be sent to /dashboard → ProtectedRoute → /auth
         * → PublicRoute (null) → flicker → then render /auth. The extra hop through
         * /dashboard created a visible redirect chain.
         *
         * Sending directly to /auth is safe: if the user IS authenticated, PublicRoute
         * will immediately redirect them on to /dashboard.
         */}
        <Route path="*" element={<Navigate to="/auth" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
