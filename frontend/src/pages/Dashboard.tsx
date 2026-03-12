import { useState, useEffect, type FC } from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../components/ui/Card';

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
        const [runsRes, statsRes] = await Promise.all([
          fetch('/api/runs?limit=5&sort=created_at:desc'),
          fetch('/api/runs/stats'),
        ]);
        if (runsRes.ok) {
          const data = await runsRes.json();
          setRecentRuns(data.runs || []);
        }
        if (statsRes.ok) {
          setStats(await statsRes.json());
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
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Deep Research System overview
          </p>
        </div>
        <Link
          to="/spaces"
          className="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
        >
          New Research
        </Link>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <p className="text-sm text-gray-500 dark:text-gray-400">Total Runs</p>
          <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">
            {stats.total_runs}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500 dark:text-gray-400">Total Cost</p>
          <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">
            ${stats.total_cost.toFixed(2)}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500 dark:text-gray-400">Active Runs</p>
          <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">
            {stats.active_runs}
          </p>
        </Card>
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Knowledge Spaces</h2>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
            Upload and index documents for semantic research.
          </p>
          <Link className="mt-4 inline-block text-blue-600 hover:text-blue-700" to="/spaces">
            Open Spaces
          </Link>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Analytics</h2>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
            Monitor costs, quality metrics, and run status.
          </p>
          <Link className="mt-4 inline-block text-blue-600 hover:text-blue-700" to="/analytics">
            Go to Analytics
          </Link>
        </Card>
      </div>

      {/* Recent runs */}
      <Card>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Recent Runs</h2>
        {loading ? (
          <p className="mt-4 text-sm text-gray-500">Loading...</p>
        ) : recentRuns.length === 0 ? (
          <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">
            No runs yet. Start a new research to see results here.
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500 dark:text-gray-400">
                  <th className="pb-2">Document</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Regime</th>
                  <th className="pb-2">Cost</th>
                  <th className="pb-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {recentRuns.map((run) => (
                  <tr key={run.id} className="border-b border-gray-100 dark:border-gray-700">
                    <td className="py-2 text-gray-900 dark:text-white">{run.doc_id}</td>
                    <td className="py-2">
                      <span className={`inline-block rounded px-2 py-0.5 text-xs ${
                        run.status === 'completed' ? 'bg-green-100 text-green-800' :
                        run.status === 'running' ? 'bg-blue-100 text-blue-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {run.status}
                      </span>
                    </td>
                    <td className="py-2 text-gray-600 dark:text-gray-400">{run.regime}</td>
                    <td className="py-2 text-gray-600 dark:text-gray-400">${run.estimated_cost.toFixed(2)}</td>
                    <td className="py-2 text-gray-500 dark:text-gray-400">
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
