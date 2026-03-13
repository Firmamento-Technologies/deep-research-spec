import { useState, useEffect, Fragment, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { AVAILABLE_MODELS } from '../constants/models'
import { api } from '../lib/api'

// ------------------------------------------------------------------ //
// Types
// ------------------------------------------------------------------ //
interface SettingsData {
  api_keys: {
    openrouter: string
  }
  model_assignments: Record<string, string>  // nodeId → modelId
  default_config: {
    preset: 'Economy' | 'Balanced' | 'Premium'
    max_budget: number
    style_profile: string
  }
  connectors: {
    perplexity: boolean
    tavily: boolean
    brave: boolean
    scraper: boolean
  }
  webhooks: {
    url: string
    events: string[]  // 'NODE_COMPLETED', 'SECTION_APPROVED', etc.
  }
}

const DEFAULT_NODE_MODELS: Record<string, string> = {
  planner: 'google/gemini-2.5-pro',
  researcher: 'perplexity/sonar-pro',
  source_synth: 'anthropic/claude-sonnet-4',
  writer_a: 'anthropic/claude-opus-4-5',
  writer_b: 'anthropic/claude-opus-4-5',
  writer_c: 'anthropic/claude-opus-4-5',
  writer_single: 'anthropic/claude-opus-4-5',
  fusor: 'openai/o3',
  post_draft_analyzer: 'google/gemini-2.5-pro',
  researcher_targeted: 'perplexity/sonar-pro',
  style_fixer: 'anthropic/claude-sonnet-4',
  r1: 'openai/o3',
  r2: 'openai/o3-mini',
  r3: 'openai/o3-mini',
  f1: 'google/gemini-2.5-pro',
  f2: 'google/gemini-2.5-pro',
  f3: 'google/gemini-2.5-pro',
  s1: 'anthropic/claude-sonnet-4',
  s2: 'anthropic/claude-haiku-3',
  s3: 'anthropic/claude-haiku-3',
  context_compressor: 'qwen/qwen3-7b',
  coherence_guard: 'google/gemini-2.5-pro',
  reflector: 'openai/o3',
  span_editor: 'anthropic/claude-sonnet-4',
}

const WEBHOOK_EVENT_OPTIONS = [
  'NODE_STARTED',
  'NODE_COMPLETED',
  'NODE_FAILED',
  'SECTION_APPROVED',
  'CSS_UPDATE',
  'BUDGET_UPDATE',
  'HUMAN_REQUIRED',
  'PIPELINE_DONE',
]

// ------------------------------------------------------------------ //
// Settings page
// ------------------------------------------------------------------ //
export function Settings() {
  const navigate = useNavigate()
  const [data, setData] = useState<SettingsData | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showApiKey, setShowApiKey] = useState(false)

  useEffect(() => {
    api.get('/api/settings')
      .then(res => setData(res.data))
      .catch(e => setError(`Errore caricamento: ${e.message}`))
  }, [])

  const handleSave = async () => {
    if (!data) return
    setSaving(true)
    setSaved(false)
    setError(null)
    try {
      await api.put('/api/settings', data)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const updateField = (path: string[], value: unknown) => {
    setData(prev => {
      if (!prev) return prev
      const copy = JSON.parse(JSON.stringify(prev))
      let ref: any = copy
      for (let i = 0; i < path.length - 1; i++) ref = ref[path[i]]
      ref[path[path.length - 1]] = value
      return copy
    })
  }

  const toggleWebhookEvent = (evt: string) => {
    setData(prev => {
      if (!prev) return prev
      const current = prev.webhooks.events
      const updated = current.includes(evt)
        ? current.filter(e => e !== evt)
        : [...current, evt]
      return { ...prev, webhooks: { ...prev.webhooks, events: updated } }
    })
  }

  if (!data) {
    return (
      <div className="p-4 md:p-6 max-w-5xl mx-auto text-drs-faint text-[12px] font-mono">
        {error ? `Errore: ${error}` : 'Caricamento impostazioni...'}
      </div>
    )
  }

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      {/* Header with back button */}
      <div className="flex items-center gap-[12px] mb-[24px]">
        <button
          onClick={() => navigate('/')}
          className="bg-transparent border border-drs-border rounded-[6px] text-drs-muted text-[12px] font-mono px-[12px] py-[6px] cursor-pointer"
          title="Torna alla home"
        >
          ← Indietro
        </button>
        <div className="text-[18px] text-drs-text font-bold">Impostazioni</div>
      </div>

      {/* API Keys */}
      <Section title="API Keys">
        <Label>OpenRouter API Key</Label>
        <div className="flex gap-[8px] items-center">
          <input
            type={showApiKey ? 'text' : 'password'}
            value={data.api_keys.openrouter}
            onChange={e => updateField(['api_keys', 'openrouter'], e.target.value)}
            placeholder="sk-or-v1-..."
            className="flex-1 bg-drs-s1 border border-drs-border rounded-input text-drs-text text-[12px] font-mono px-[10px] py-[7px] outline-none"
          />
          <button
            onClick={() => setShowApiKey(o => !o)}
            className="bg-transparent border border-drs-border rounded-input text-drs-muted text-[11px] font-mono px-[12px] py-[6px] cursor-pointer"
          >
            {showApiKey ? 'Nascondi' : 'Mostra'}
          </button>
        </div>
      </Section>

      {/* Model Assignments */}
      <Section title="Assegnazione Modelli">
        <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-[8px] items-center">
          {Object.entries(DEFAULT_NODE_MODELS).map(([nodeId, defaultModel]) => {
            const current = data.model_assignments[nodeId] ?? defaultModel
            return (
              <Fragment key={nodeId}>
                <Label>{nodeId.replace(/_/g, ' ').toUpperCase()}</Label>
                <select
                  value={current}
                  onChange={e => updateField(['model_assignments', nodeId], e.target.value)}
                  className="bg-drs-s1 border border-drs-border rounded-input text-drs-text text-[12px] font-mono px-[10px] py-[6px] outline-none"
                >
                  {AVAILABLE_MODELS.map(m => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({m.provider}) — ${m.costIn}/{m.costOut}
                    </option>
                  ))}
                </select>
              </Fragment>
            )
          })}
        </div>
      </Section>

      {/* Default Config */}
      <Section title="Configurazione di Default">
        <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-[12px] items-center">
          <Label>Preset predefinito</Label>
          <select
            value={data.default_config.preset}
            onChange={e => updateField(['default_config', 'preset'], e.target.value)}
            className="bg-drs-s1 border border-drs-border rounded-input text-drs-text text-[12px] font-mono px-[10px] py-[6px] outline-none"
          >
            <option value="Economy">Economy</option>
            <option value="Balanced">Balanced</option>
            <option value="Premium">Premium</option>
          </select>

          <Label>Budget massimo ($)</Label>
          <input
            type="number"
            value={data.default_config.max_budget}
            onChange={e => updateField(['default_config', 'max_budget'], parseFloat(e.target.value))}
            min={1}
            max={1000}
            step={5}
            className="bg-drs-s1 border border-drs-border rounded-input text-drs-text text-[12px] font-mono px-[10px] py-[6px] outline-none w-[120px]"
          />

          <Label>Profilo stile</Label>
          <select
            value={data.default_config.style_profile}
            onChange={e => updateField(['default_config', 'style_profile'], e.target.value)}
            className="bg-drs-s1 border border-drs-border rounded-input text-drs-text text-[12px] font-mono px-[10px] py-[6px] outline-none"
          >
            <option value="academic">Academic</option>
            <option value="technical">Technical</option>
            <option value="journalistic">Journalistic</option>
            <option value="conversational">Conversational</option>
          </select>
        </div>
      </Section>

      {/* Connectors */}
      <Section title="Connettori">
        <div className="flex flex-col gap-[8px]">
          {['perplexity', 'tavily', 'brave', 'scraper'].map(conn => (
            <label key={conn} className="flex items-center gap-[10px] cursor-pointer">
              <input
                type="checkbox"
                checked={data.connectors[conn as keyof typeof data.connectors]}
                onChange={e => updateField(['connectors', conn], e.target.checked)}
                className="cursor-pointer"
              />
              <span className="text-[12px] font-mono text-drs-text">
                {conn.charAt(0).toUpperCase() + conn.slice(1)}
              </span>
            </label>
          ))}
        </div>
      </Section>

      {/* Webhooks */}
      <Section title="Webhooks">
        <Label>URL Webhook</Label>
        <input
          type="url"
          value={data.webhooks.url}
          onChange={e => updateField(['webhooks', 'url'], e.target.value)}
          placeholder="https://your-server.com/webhook"
          className="bg-drs-s1 border border-drs-border rounded-input text-drs-text text-[12px] font-mono px-[10px] py-[7px] outline-none w-full mb-[12px]"
        />
        <Label>Eventi da inviare</Label>
        <div className="grid grid-cols-2 gap-[6px]">
          {WEBHOOK_EVENT_OPTIONS.map(evt => (
            <label key={evt} className="flex items-center gap-[8px] cursor-pointer">
              <input
                type="checkbox"
                checked={data.webhooks.events.includes(evt)}
                onChange={() => toggleWebhookEvent(evt)}
                className="cursor-pointer"
              />
              <span className="text-[11px] font-mono text-drs-muted">{evt}</span>
            </label>
          ))}
        </div>
      </Section>

      {/* Save button */}
      <div className="mt-[24px] pt-[20px] border-t border-drs-border flex gap-[12px] items-center">
        {error && <span className="text-[11px] text-drs-red font-mono">{error}</span>}
        {saved && <span className="text-[11px] text-drs-green font-mono">✓ Salvato</span>}
        <div className="ml-auto flex gap-[8px]">
          <button
            onClick={() => window.location.reload()}
            className="bg-transparent border border-drs-border rounded-[6px] text-drs-muted text-[12px] font-mono px-[16px] py-[8px] cursor-pointer"
          >
            Annulla
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-drs-accent border-none rounded-[6px] text-drs-bg text-[12px] font-mono font-bold px-[20px] py-[8px]"
            style={{
              cursor: saving ? 'not-allowed' : 'pointer',
              opacity: saving ? 0.5 : 1,
            }}
          >
            {saving ? 'Salvataggio...' : 'Salva Impostazioni'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ //
// Helper components
// ------------------------------------------------------------------ //
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="bg-drs-s1 border border-drs-border rounded-card px-[20px] py-[16px] mb-[16px]">
      <div className="text-[11px] font-mono text-drs-faint tracking-[1px] mb-[14px]">
        {title.toUpperCase()}
      </div>
      {children}
    </div>
  )
}

function Label({ children }: { children: ReactNode }) {
  return (
    <span className="text-[12px] font-mono text-drs-muted">
      {children}
    </span>
  )
}
