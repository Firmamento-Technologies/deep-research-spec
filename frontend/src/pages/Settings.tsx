import React, { useState, useEffect } from 'react'
import { AVAILABLE_MODELS } from '../constants/models'

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
  planner:              'google/gemini-2.5-pro',
  researcher:           'perplexity/sonar-pro',
  source_synth:         'anthropic/claude-sonnet-4',
  writer_a:             'anthropic/claude-opus-4-5',
  writer_b:             'anthropic/claude-opus-4-5',
  writer_c:             'anthropic/claude-opus-4-5',
  writer_single:        'anthropic/claude-opus-4-5',
  fusor:                'openai/o3',
  post_draft_analyzer:  'google/gemini-2.5-pro',
  researcher_targeted:  'perplexity/sonar-pro',
  style_fixer:          'anthropic/claude-sonnet-4',
  r1: 'openai/o3',
  r2: 'openai/o3-mini',
  r3: 'openai/o3-mini',
  f1: 'google/gemini-2.5-pro',
  f2: 'google/gemini-2.5-pro',
  f3: 'google/gemini-2.5-pro',
  s1: 'anthropic/claude-sonnet-4',
  s2: 'anthropic/claude-haiku-3',
  s3: 'anthropic/claude-haiku-3',
  context_compressor:   'qwen/qwen3-7b',
  coherence_guard:      'google/gemini-2.5-pro',
  reflector:            'openai/o3',
  span_editor:          'anthropic/claude-sonnet-4',
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
  const [data, setData]       = useState<SettingsData | null>(null)
  const [saving, setSaving]   = useState(false)
  const [saved, setSaved]     = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const [showApiKey, setShowApiKey] = useState(false)

  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.json())
      .then(json => setData(json))
      .catch(e => setError(`Errore caricamento: ${e.message}`))
  }, [])

  const handleSave = async () => {
    if (!data) return
    setSaving(true)
    setSaved(false)
    setError(null)
    try {
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
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
      <div style={{ flex: 1, background: '#0A0B0F', padding: 28, color: '#50536A', fontSize: 12, fontFamily: 'monospace' }}>
        {error ? `Errore: ${error}` : 'Caricamento impostazioni…'}
      </div>
    )
  }

  return (
    <div style={{ flex: 1, background: '#0A0B0F', overflowY: 'auto', padding: '20px 28px' }}>
      <div style={{ fontSize: 18, color: '#F0F1F6', fontWeight: 700, marginBottom: 24 }}>Impostazioni</div>

      {/* API Keys */}
      <Section title="API Keys">
        <Label>OpenRouter API Key</Label>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type={showApiKey ? 'text' : 'password'}
            value={data.api_keys.openrouter}
            onChange={e => updateField(['api_keys', 'openrouter'], e.target.value)}
            placeholder="sk-or-v1-..."
            style={{
              flex: 1,
              background: '#111318',
              border: '1px solid #2A2D3A',
              borderRadius: 4,
              color: '#F0F1F6',
              fontSize: 12,
              fontFamily: 'monospace',
              padding: '7px 10px',
              outline: 'none',
            }}
          />
          <button
            onClick={() => setShowApiKey(o => !o)}
            style={{
              background: 'transparent',
              border: '1px solid #2A2D3A',
              borderRadius: 4,
              color: '#8B8FA8',
              fontSize: 11,
              fontFamily: 'monospace',
              padding: '6px 12px',
              cursor: 'pointer',
            }}
          >
            {showApiKey ? 'Nascondi' : 'Mostra'}
          </button>
        </div>
      </Section>

      {/* Model Assignments */}
      <Section title="Assegnazione Modelli">
        <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 8, alignItems: 'center' }}>
          {Object.entries(DEFAULT_NODE_MODELS).map(([nodeId, defaultModel]) => {
            const current = data.model_assignments[nodeId] ?? defaultModel
            return (
              <React.Fragment key={nodeId}>
                <Label>{nodeId.replace(/_/g, ' ').toUpperCase()}</Label>
                <select
                  value={current}
                  onChange={e => updateField(['model_assignments', nodeId], e.target.value)}
                  style={{
                    background: '#111318',
                    border: '1px solid #2A2D3A',
                    borderRadius: 4,
                    color: '#F0F1F6',
                    fontSize: 12,
                    fontFamily: 'monospace',
                    padding: '6px 10px',
                    outline: 'none',
                  }}
                >
                  {AVAILABLE_MODELS.map(m => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({m.provider}) — ${m.costIn}/{m.costOut}
                    </option>
                  ))}
                </select>
              </React.Fragment>
            )
          })}
        </div>
      </Section>

      {/* Default Config */}
      <Section title="Configurazione di Default">
        <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 12, alignItems: 'center' }}>
          <Label>Preset predefinito</Label>
          <select
            value={data.default_config.preset}
            onChange={e => updateField(['default_config', 'preset'], e.target.value)}
            style={{
              background: '#111318',
              border: '1px solid #2A2D3A',
              borderRadius: 4,
              color: '#F0F1F6',
              fontSize: 12,
              fontFamily: 'monospace',
              padding: '6px 10px',
              outline: 'none',
            }}
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
            style={{
              background: '#111318',
              border: '1px solid #2A2D3A',
              borderRadius: 4,
              color: '#F0F1F6',
              fontSize: 12,
              fontFamily: 'monospace',
              padding: '6px 10px',
              outline: 'none',
              width: 120,
            }}
          />

          <Label>Profilo stile</Label>
          <select
            value={data.default_config.style_profile}
            onChange={e => updateField(['default_config', 'style_profile'], e.target.value)}
            style={{
              background: '#111318',
              border: '1px solid #2A2D3A',
              borderRadius: 4,
              color: '#F0F1F6',
              fontSize: 12,
              fontFamily: 'monospace',
              padding: '6px 10px',
              outline: 'none',
            }}
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {['perplexity', 'tavily', 'brave', 'scraper'].map(conn => (
            <label key={conn} style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={data.connectors[conn as keyof typeof data.connectors]}
                onChange={e => updateField(['connectors', conn], e.target.checked)}
                style={{ cursor: 'pointer' }}
              />
              <span style={{ fontSize: 12, fontFamily: 'monospace', color: '#F0F1F6' }}>
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
          style={{
            background: '#111318',
            border: '1px solid #2A2D3A',
            borderRadius: 4,
            color: '#F0F1F6',
            fontSize: 12,
            fontFamily: 'monospace',
            padding: '7px 10px',
            outline: 'none',
            width: '100%',
            marginBottom: 12,
          }}
        />
        <Label>Eventi da inviare</Label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6 }}>
          {WEBHOOK_EVENT_OPTIONS.map(evt => (
            <label key={evt} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={data.webhooks.events.includes(evt)}
                onChange={() => toggleWebhookEvent(evt)}
                style={{ cursor: 'pointer' }}
              />
              <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#8B8FA8' }}>{evt}</span>
            </label>
          ))}
        </div>
      </Section>

      {/* Save button */}
      <div
        style={{
          marginTop: 24,
          paddingTop: 20,
          borderTop: '1px solid #2A2D3A',
          display: 'flex',
          gap: 12,
          alignItems: 'center',
        }}
      >
        {error && <span style={{ fontSize: 11, color: '#EF4444', fontFamily: 'monospace' }}>{error}</span>}
        {saved && <span style={{ fontSize: 11, color: '#22C55E', fontFamily: 'monospace' }}>✓ Salvato</span>}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button
            onClick={() => window.location.reload()}
            style={{
              background: 'transparent',
              border: '1px solid #2A2D3A',
              borderRadius: 6,
              color: '#8B8FA8',
              fontSize: 12,
              fontFamily: 'monospace',
              padding: '8px 16px',
              cursor: 'pointer',
            }}
          >
            Annulla
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              background: '#7C8CFF',
              border: 'none',
              borderRadius: 6,
              color: '#0A0B0F',
              fontSize: 12,
              fontFamily: 'monospace',
              fontWeight: 700,
              padding: '8px 20px',
              cursor: saving ? 'not-allowed' : 'pointer',
              opacity: saving ? 0.5 : 1,
            }}
          >
            {saving ? 'Salvataggio…' : 'Salva Impostazioni'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ //
// Helper components
// ------------------------------------------------------------------ //
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: '#111318',
        border: '1px solid #2A2D3A',
        borderRadius: 8,
        padding: '16px 20px',
        marginBottom: 16,
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontFamily: 'monospace',
          color: '#50536A',
          letterSpacing: 1,
          marginBottom: 14,
        }}
      >
        {title.toUpperCase()}
      </div>
      {children}
    </div>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <span style={{ fontSize: 12, fontFamily: 'monospace', color: '#8B8FA8' }}>
      {children}
    </span>
  )
}
