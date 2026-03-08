import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LoginPage } from './pages/Login';
import { RegisterPage } from './pages/Register';
import { Dashboard } from './pages/Dashboard';
import { KnowledgeSpaces } from './pages/KnowledgeSpaces';
import { SpaceDetail } from './pages/SpaceDetail';
import { SpaceSearch } from './pages/SpaceSearch';
import { Analytics } from './pages/Analytics';
import { Settings } from './pages/Settings';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <AuthProvider>
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
                  <div>Admin Users Management</div>
                </ProtectedRoute>
              }
            />

            {/* Redirects */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </AuthProvider>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
