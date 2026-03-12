import { useState, useEffect, type FC } from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../components/ui/Card';
import { api } from '../lib/api';

interface RunSummary {
  id: string;
  doc_id: string;
  status: string;
  regime: string;
  estimated_cost: number;
  created_at: string;
}

interface DashboardStats {
  total_runs: number;
  total_cost: number;
  active_runs: number;
}

export const Dashboard: FC = () => {
  const [recentRuns, setRecentRuns] = useState<RunSummary[]>([]);
  const [stats, setStats] = useState<DashboardStats>({ total_runs: 0, total_cost: 0, active_runs: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchDashboard() {
      try {
        const [runsRes, statsRes] = await Promise.allSettled([
          api.get('/api/runs', { params: { limit: 5, sort: 'created_at:desc' } }),
          api.get('/api/runs/stats'),
        ]);
        if (runsRes.status === 'fulfilled') {
          setRecentRuns(runsRes.value.data?.runs || []);
        }
        if (statsRes.status === 'fulfilled') {
          setStats(statsRes.value.data);
        }
      } catch {
        // API not available — show empty state
      } finally {
        setLoading(false);
      }
    }
    fetchDashboard();
  }, []);

  return (
    <div className="mx-auto max-w-6xl p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-drs-text">Dashboard</h1>
          <p className="mt-2 text-drs-muted">
            Deep Research System overview
          </p>
        </div>
        <Link
          to="/spaces"
          className="rounded-lg bg-drs-accent px-4 py-2 text-white hover:brightness-110 transition"
        >
          New Research
        </Link>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <p className="text-sm text-drs-muted">Total Runs</p>
          <p className="mt-1 text-2xl font-semibold text-drs-text">
            {stats.total_runs}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-drs-muted">Total Cost</p>
          <p className="mt-1 text-2xl font-semibold text-drs-text">
            ${stats.total_cost.toFixed(2)}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-drs-muted">Active Runs</p>
          <p className="mt-1 text-2xl font-semibold text-drs-text">
            {stats.active_runs}
          </p>
        </Card>
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <h2 className="text-lg font-semibold text-drs-text">Knowledge Spaces</h2>
          <p className="mt-2 text-sm text-drs-muted">
            Upload and index documents for semantic research.
          </p>
          <Link className="mt-4 inline-block text-drs-accent hover:brightness-110" to="/spaces">
            Open Spaces
          </Link>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold text-drs-text">Analytics</h2>
          <p className="mt-2 text-sm text-drs-muted">
            Monitor costs, quality metrics, and run status.
          </p>
          <Link className="mt-4 inline-block text-drs-accent hover:brightness-110" to="/analytics">
            Go to Analytics
          </Link>
        </Card>
      </div>

      {/* Recent runs */}
      <Card>
        <h2 className="text-lg font-semibold text-drs-text">Recent Runs</h2>
        {loading ? (
          <p className="mt-4 text-sm text-drs-faint">Loading...</p>
        ) : recentRuns.length === 0 ? (
          <p className="mt-4 text-sm text-drs-muted">
            No runs yet. Start a new research to see results here.
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-drs-border text-left text-drs-muted">
                  <th className="pb-2">Document</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Regime</th>
                  <th className="pb-2">Cost</th>
                  <th className="pb-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {recentRuns.map((run) => (
                  <tr key={run.id} className="border-b border-drs-border">
                    <td className="py-2 text-drs-text">{run.doc_id}</td>
                    <td className="py-2">
                      <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${
                        run.status === 'completed' ? 'bg-drs-green/20 text-drs-green' :
                        run.status === 'running' ? 'bg-drs-accent/20 text-drs-accent' :
                        'bg-drs-s3 text-drs-muted'
                      }`}>
                        {run.status}
                      </span>
                    </td>
                    <td className="py-2 text-drs-muted">{run.regime}</td>
                    <td className="py-2 text-drs-muted">${run.estimated_cost.toFixed(2)}</td>
                    <td className="py-2 text-drs-faint">
                      {new Date(run.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
};
