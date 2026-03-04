import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { RunList } from './pages/RunList';
import { RunDetail } from './pages/RunDetail';
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
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="runs" element={<RunList />} />
            <Route path="runs/:id" element={<RunDetail />} />
            
            {/* Knowledge Spaces */}
            <Route path="spaces" element={<KnowledgeSpaces />} />
            <Route path="spaces/:id" element={<SpaceDetail />} />
            <Route path="spaces/:id/search" element={<SpaceSearch />} />
            
            <Route path="analytics" element={<Analytics />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
