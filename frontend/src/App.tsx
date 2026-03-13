import { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from './lib/query';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { ErrorBoundary } from './components/ErrorBoundary';
import { LoginPage } from './pages/Login';
import { RegisterPage } from './pages/Register';
import { AppShell } from './components/layout/AppShell';

// Code splitting — lazy-loaded pages
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
const KnowledgeSpaces = lazy(() => import('./pages/KnowledgeSpaces').then(m => ({ default: m.KnowledgeSpaces })));
const SpaceDetail = lazy(() => import('./pages/SpaceDetail').then(m => ({ default: m.SpaceDetail })));
const SpaceSearch = lazy(() => import('./pages/SpaceSearch').then(m => ({ default: m.SpaceSearch })));
const Analytics = lazy(() => import('./pages/Analytics').then(m => ({ default: m.Analytics })));
const Settings = lazy(() => import('./pages/Settings').then(m => ({ default: m.Settings })));
const AdminUsers = lazy(() => import('./pages/AdminUsers').then(m => ({ default: m.AdminUsers })));
const NewResearch = lazy(() => import('./pages/NewResearch').then(m => ({ default: m.NewResearch })));

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
    <div className="flex justify-center items-center h-screen bg-drs-bg">
      <div className="text-drs-muted font-mono text-sm">Loading...</div>
    </div>
  );
}

/** Layout wrapper: ProtectedRoute + AppShell with Outlet for child pages */
function ProtectedLayout({ requiredRole }: { requiredRole?: 'admin' | 'user' | 'viewer' }) {
  return (
    <ProtectedRoute requiredRole={requiredRole}>
      <AppShell />
    </ProtectedRoute>
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

                {/* Protected routes — all wrapped in AppShell layout */}
                <Route element={<ProtectedLayout />}>
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/new-research" element={<NewResearch />} />
                  <Route path="/spaces" element={<KnowledgeSpaces />} />
                  <Route path="/spaces/:spaceId" element={<SpaceDetail />} />
                  <Route path="/spaces/:spaceId/search" element={<SpaceSearch />} />
                  <Route path="/analytics" element={<Analytics />} />
                  <Route path="/settings" element={<Settings />} />
                </Route>

                {/* Admin-only routes */}
                <Route element={<ProtectedLayout requiredRole="admin" />}>
                  <Route path="/admin/users" element={<AdminUsers />} />
                </Route>

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
