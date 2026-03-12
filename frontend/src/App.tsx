import { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from './lib/query';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { ErrorBoundary } from './components/ErrorBoundary';
import { LoginPage } from './pages/Login';
import { RegisterPage } from './pages/Register';

// Code splitting — lazy-loaded pages
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
const KnowledgeSpaces = lazy(() => import('./pages/KnowledgeSpaces').then(m => ({ default: m.KnowledgeSpaces })));
const SpaceDetail = lazy(() => import('./pages/SpaceDetail').then(m => ({ default: m.SpaceDetail })));
const SpaceSearch = lazy(() => import('./pages/SpaceSearch').then(m => ({ default: m.SpaceSearch })));
const Analytics = lazy(() => import('./pages/Analytics').then(m => ({ default: m.Analytics })));
const Settings = lazy(() => import('./pages/Settings').then(m => ({ default: m.Settings })));
const AdminUsers = lazy(() => import('./pages/AdminUsers').then(m => ({ default: m.AdminUsers })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function LoadingFallback() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
      <div>Loading...</div>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <AuthProvider>
          <ErrorBoundary>
            <Suspense fallback={<LoadingFallback />}>
              <Routes>
                {/* Public routes */}
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register" element={<RegisterPage />} />

                {/* Protected routes */}
                <Route
                  path="/dashboard"
                  element={
                    <ProtectedRoute>
                      <Dashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/spaces"
                  element={
                    <ProtectedRoute>
                      <KnowledgeSpaces />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/spaces/:spaceId"
                  element={
                    <ProtectedRoute>
                      <SpaceDetail />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/spaces/:spaceId/search"
                  element={
                    <ProtectedRoute>
                      <SpaceSearch />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/analytics"
                  element={
                    <ProtectedRoute>
                      <Analytics />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/settings"
                  element={
                    <ProtectedRoute>
                      <Settings />
                    </ProtectedRoute>
                  }
                />

                {/* Admin-only routes */}
                <Route
                  path="/admin/users"
                  element={
                    <ProtectedRoute requiredRole="admin">
                      <AdminUsers />
                    </ProtectedRoute>
                  }
                />

                {/* Redirects */}
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </AuthProvider>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
