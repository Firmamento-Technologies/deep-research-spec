import { useState, useEffect, useCallback, type FC } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { api } from '../lib/api';
import { useAppStore } from '../store/useAppStore';
import { useRunStore } from '../store/useRunStore';
import type { QualityPreset, RunState } from '../types/run';

interface KnowledgeSpace {
  id: string;
  name: string;
  description?: string;
  source_count: number;
}

const PRESETS: { value: QualityPreset; label: string; desc: string; color: string }[] = [
  { value: 'Economy', label: 'Economy', desc: 'Veloce, costo minimo. Ideale per bozze e test.', color: 'border-green-500' },
  { value: 'Balanced', label: 'Balanced', desc: 'Buon equilibrio tra qualita e costo.', color: 'border-blue-500' },
  { value: 'Premium', label: 'Premium', desc: 'Massima qualita, piu iterazioni, costo elevato.', color: 'border-purple-500' },
];

export const NewResearch: FC = () => {
  const navigate = useNavigate();
  const setState = useAppStore((s) => s.setState);
  const setActiveDocId = useAppStore((s) => s.setActiveDocId);
  const setActiveRun = useRunStore((s) => s.setActiveRun);

  const [topic, setTopic] = useState('');
  const [qualityPreset, setQualityPreset] = useState<QualityPreset>('Balanced');
  const [targetWords, setTargetWords] = useState(5000);
  const [maxBudget, setMaxBudget] = useState(50);
  const [styleProfile, setStyleProfile] = useState('academic');
  const [knowledgeSpaceId, setKnowledgeSpaceId] = useState<string | ''>('');
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch available knowledge spaces
  useEffect(() => {
    api.get('/api/spaces')
      .then((res) => setSpaces(res.data ?? []))
      .catch(() => {});
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!topic.trim()) return;
    setIsSubmitting(true);
    setError(null);

    try {
      const params = {
        topic: topic.trim(),
        quality_preset: qualityPreset,
        target_words: targetWords,
        max_budget: maxBudget,
        style_profile: styleProfile,
        knowledge_space_id: knowledgeSpaceId || undefined,
      };

      const res = await api.post('/api/runs', params);
      const docId = res.data.doc_id;

      // Update app state to show pipeline
      setActiveDocId(docId);
      setState('PROCESSING');
      setActiveRun({
        docId,
        topic: topic.trim(),
        status: 'initializing',
        qualityPreset,
        targetWords,
        maxBudget,
        budgetSpent: 0,
        budgetRemainingPct: 100,
        totalSections: 0,
        currentSection: 0,
        currentIteration: 0,
        nodes: {},
        cssScores: { content: 0, style: 0, source: 0 },
        juryVerdicts: [],
        sections: [],
        shineActive: false,
        rlmMode: false,
        hardStopFired: false,
        oscillationDetected: false,
        forceApprove: false,
        outputPaths: undefined,
      } as RunState);

      // Navigate to dashboard where pipeline will show
      navigate('/dashboard');
    } catch (err: any) {
      setError(err?.message || 'Errore durante la creazione della ricerca.');
    } finally {
      setIsSubmitting(false);
    }
  }, [topic, qualityPreset, targetWords, maxBudget, styleProfile, knowledgeSpaceId,
      navigate, setState, setActiveDocId, setActiveRun]);

  const inputClass =
    'w-full px-3 py-2 bg-drs-s2 border border-drs-border rounded-lg text-drs-text placeholder-drs-faint focus:ring-2 focus:ring-drs-accent focus:border-drs-accent outline-none text-sm';

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-drs-text">Nuova Ricerca</h1>
        <p className="mt-2 text-drs-muted">
          Configura e avvia un nuovo documento di ricerca approfondita
        </p>
      </div>

      <div className="space-y-6">
        {/* Topic */}
        <Card>
          <label className="block text-sm font-medium text-drs-text mb-2">
            Argomento della ricerca *
          </label>
          <textarea
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            className={inputClass + ' min-h-[80px]'}
            placeholder="es. L'impatto dell'intelligenza artificiale nella diagnostica medica: stato dell'arte e prospettive future"
            rows={3}
          />
          <p className="mt-1 text-xs text-drs-faint">
            Descrivi l'argomento in modo dettagliato per ottenere risultati migliori
          </p>
        </Card>

        {/* Quality Preset */}
        <Card>
          <label className="block text-sm font-medium text-drs-text mb-3">
            Preset qualita
          </label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {PRESETS.map((p) => (
              <button
                key={p.value}
                onClick={() => setQualityPreset(p.value)}
                className={
                  'p-4 rounded-lg border-2 text-left transition-all ' +
                  (qualityPreset === p.value
                    ? `${p.color} bg-drs-s2`
                    : 'border-drs-border hover:border-drs-border-bright bg-drs-s1')
                }
              >
                <div className="font-semibold text-drs-text text-sm">{p.label}</div>
                <div className="text-xs text-drs-muted mt-1">{p.desc}</div>
              </button>
            ))}
          </div>
        </Card>

        {/* Parameters row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Target Words */}
          <Card>
            <label className="block text-sm font-medium text-drs-text mb-2">
              Parole target
            </label>
            <input
              type="number"
              value={targetWords}
              onChange={(e) => setTargetWords(Number(e.target.value))}
              min={1000}
              max={50000}
              step={1000}
              className={inputClass}
            />
            <p className="mt-1 text-xs text-drs-faint">1.000 - 50.000</p>
          </Card>

          {/* Max Budget */}
          <Card>
            <label className="block text-sm font-medium text-drs-text mb-2">
              Budget massimo ($)
            </label>
            <input
              type="number"
              value={maxBudget}
              onChange={(e) => setMaxBudget(Number(e.target.value))}
              min={1}
              max={1000}
              step={5}
              className={inputClass}
            />
            <p className="mt-1 text-xs text-drs-faint">$1 - $1.000</p>
          </Card>

          {/* Style Profile */}
          <Card>
            <label className="block text-sm font-medium text-drs-text mb-2">
              Stile di scrittura
            </label>
            <select
              value={styleProfile}
              onChange={(e) => setStyleProfile(e.target.value)}
              className={inputClass}
            >
              <option value="academic">Accademico</option>
              <option value="business">Business</option>
              <option value="journalistic">Giornalistico</option>
              <option value="technical">Tecnico</option>
              <option value="narrative">Narrativo</option>
            </select>
          </Card>
        </div>

        {/* Knowledge Space */}
        <Card>
          <label className="block text-sm font-medium text-drs-text mb-2">
            Knowledge Space (opzionale)
          </label>
          <select
            value={knowledgeSpaceId}
            onChange={(e) => setKnowledgeSpaceId(e.target.value)}
            className={inputClass}
          >
            <option value="">Nessuno — usa solo fonti web</option>
            {spaces.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.source_count} documenti)
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-drs-faint">
            Seleziona un knowledge space per includere documenti caricati come fonti aggiuntive
          </p>
        </Card>

        {/* Error */}
        {error && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Submit */}
        <div className="flex justify-end gap-3">
          <Button variant="ghost" onClick={() => navigate('/dashboard')}>
            Annulla
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!topic.trim() || isSubmitting}
          >
            {isSubmitting ? 'Avvio in corso...' : 'Avvia Ricerca'}
          </Button>
        </div>
      </div>
    </div>
  );
};
