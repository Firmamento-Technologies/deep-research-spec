import type { FC } from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../components/ui/Card';

export const Dashboard: FC = () => {
  return (
    <div className="mx-auto max-w-6xl p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Benvenuto in Deep Research System. Da qui puoi creare e gestire i tuoi knowledge spaces.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Knowledge Spaces</h2>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">Carica e indicizza documenti per la ricerca semantica.</p>
          <Link className="mt-4 inline-block text-blue-600 hover:text-blue-700" to="/spaces">
            Apri Spaces →
          </Link>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Analytics</h2>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">Monitora costi, qualità e stato delle esecuzioni.</p>
          <Link className="mt-4 inline-block text-blue-600 hover:text-blue-700" to="/analytics">
            Vai ad Analytics →
          </Link>
        </Card>
      </div>
    </div>
  );
};
