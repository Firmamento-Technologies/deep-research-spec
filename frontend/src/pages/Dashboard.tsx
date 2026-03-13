import { useState, useEffect, type FC } from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../components/ui/Card';
import { api } from '../lib/api';
import { useRunStore } from '../store/useRunStore';
import { useAppStore } from '../store/useAppStore';

interface RunListItem {
  doc_id: string;
  topic: string;
  status: string;
  quality_preset: string;
  total_cost: number;
  created_at: string | null;
  completed_at: string | null;
}

export const Dashboard: FC = () => {
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const activeRun = useRunStore((s) => s.activeRun);
  const setState = useAppStore((s) => s.setState);

  useEffect(() => {
    async function fetchRuns() {
      try {
        const res = await api.get('/api/runs');
        setRuns(Array.isArray(res.data) ? res.data : []);
      } catch (err) {
        console.warn('[Dashboard] failed to load runs:', err)
      } finally {
        setLoading(false);
      }
    }
    fetchRuns();
  }, []);

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      completed: 'bg-drs-green/20 text-drs-green',
      running: 'bg-drs-accent/20 text-drs-accent',
      initializing: 'bg-yellow-500/20 text-yellow-400',
      failed: 'bg-red-500/20 text-red-400',
    };
    return (
      <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${colors[status] || 'bg-drs-s3 text-drs-muted'}`}>
        {status}
      </span>
    );
  };

  return (
    <div className="mx-auto max-w-6xl p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-drs-text">Dashboard</h1>
          <p className="mt-2 text-drs-muted">Deep Research System</p>
        </div>
        <Link
          to="/new-research"
          className="rounded-lg bg-drs-accent px-4 py-2 text-white font-medium hover:brightness-110 transition"
        >
          + Nuova Ricerca
        </Link>
      </div>

      {/* Active run banner */}
      {activeRun && (
        <Card className="border-drs-accent/30 bg-drs-accent/5">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-drs-green animate-pulse" />
                <h3 className="font-semibold text-drs-text">Ricerca in corso</h3>
              </div>
              <p className="text-sm text-drs-muted mt-1">
                {activeRun.topic}
              </p>
              <div className="flex gap-4 mt-2 text-xs text-drs-faint">
                <span>Sezione {activeRun.currentSection}/{activeRun.totalSections}</span>
                <span>Iterazione {activeRun.currentIteration}</span>
                <span>${activeRun.budgetSpent.toFixed(2)} / ${activeRun.maxBudget}</span>
                <span>Preset: {activeRun.qualityPreset}</span>
              </div>
            </div>
            {activeRun.status !== 'completed' && activeRun.status !== 'failed' && (
              <button
                onClick={() => setState('PROCESSING')}
                className="rounded-lg bg-drs-accent px-4 py-2 text-white text-sm font-medium hover:brightness-110 transition"
              >
                Mostra Pipeline
              </button>
            )}
            {(activeRun.status === 'completed' || activeRun.status === 'failed') && (
              <Link
                to={`/runs/${activeRun.docId}`}
                className="rounded-lg bg-drs-s2 border border-drs-border px-4 py-2 text-drs-text text-sm font-medium hover:bg-drs-s3 transition"
              >
                Vedi Risultati
              </Link>
            )}
          </div>
        </Card>
      )}

      {/* Quick actions */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Link to="/new-research">
          <Card className="hover:border-drs-accent/30 transition-colors cursor-pointer">
            <div className="text-2xl mb-2">+</div>
            <h2 className="text-lg font-semibold text-drs-text">Nuova Ricerca</h2>
            <p className="mt-1 text-sm text-drs-muted">
              Configura topic, budget, preset e avvia
            </p>
          </Card>
        </Link>

        <Link to="/spaces">
          <Card className="hover:border-drs-accent/30 transition-colors cursor-pointer">
            <div className="text-2xl mb-2">&#128194;</div>
            <h2 className="text-lg font-semibold text-drs-text">Knowledge Spaces</h2>
            <p className="mt-1 text-sm text-drs-muted">
              Carica documenti come fonti per la ricerca
            </p>
          </Card>
        </Link>

        <Link to="/analytics">
          <Card className="hover:border-drs-accent/30 transition-colors cursor-pointer">
            <div className="text-2xl mb-2">&#128200;</div>
            <h2 className="text-lg font-semibold text-drs-text">Analytics</h2>
            <p className="mt-1 text-sm text-drs-muted">
              Costi, qualita, metriche e stato dei run
            </p>
          </Card>
        </Link>
      </div>

      {/* Recent runs */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-drs-text">Ricerche recenti</h2>
        </div>
        {loading ? (
          <p className="text-sm text-drs-faint">Caricamento...</p>
        ) : runs.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-drs-muted">
              Nessuna ricerca ancora. Clicca "Nuova Ricerca" per iniziare.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-drs-border text-left text-drs-muted">
                  <th className="pb-2">Topic</th>
                  <th className="pb-2">Stato</th>
                  <th className="pb-2">Preset</th>
                  <th className="pb-2">Costo</th>
                  <th className="pb-2">Data</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.doc_id} className="border-b border-drs-border hover:bg-drs-s1/50">
                    <td className="py-2 text-drs-text max-w-xs truncate">
                      <Link
                        to={`/runs/${run.doc_id}`}
                        className="hover:text-drs-accent transition-colors"
                      >
                        {run.topic || run.doc_id}
                      </Link>
                    </td>
                    <td className="py-2">{statusBadge(run.status)}</td>
                    <td className="py-2 text-drs-muted">{run.quality_preset}</td>
                    <td className="py-2 text-drs-muted">${run.total_cost.toFixed(2)}</td>
                    <td className="py-2 text-drs-faint">
                      {run.created_at ? new Date(run.created_at).toLocaleDateString() : '-'}
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
