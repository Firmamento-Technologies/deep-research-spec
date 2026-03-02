// Settings page — Route: /settings
// Spec: UI_BUILD_PLAN.md Section 12.
//
// Sections:
//   1. API Keys       — OpenRouter key (password + show/hide)
//   2. Model Assignments — one row per agent, model dropdown
//   3. Default Config — preset, budget, style profile
//   4. Connectors     — Perplexity / Tavily / Brave / Scraper toggles
//   5. Webhooks       — URL + event type checkboxes
// Save: PUT /api/settings (endpoint in STEP 12)

import { useState } from 'react'
import { AVAILABLE_MODELS, MODELS_BY_PROVIDER, DEFAULT_MODEL_ASSIGNMENTS } from '../constants/models'
import { api } from '../lib/api'

const AGENT_ROWS = [
  { label: 'Planner',             nodeId: 'planner'             },
  { label: 'Researcher',          nodeId: 'researcher'          },
  { label: 'Researcher Targeted', nodeId: 'researcher_targeted' },
  { label: 'Source Synthesizer',  nodeId: 'source_synth'        },
  { label: 'Writer A (Coverage)', nodeId: 'writer_a'            },
  { label: 'Writer B (Argument)', nodeId: 'writer_b'            },
  { label: 'Writer C (Readab.)',  nodeId: 'writer_c'            },
  { label: 'Writer Single',       nodeId: 'writer_single'       },
  { label: 'Fusor',               nodeId: 'fusor'               },
  { label: 'Post Draft Analyzer', nodeId: 'post_draft_analyzer' },
  { label: 'Style Fixer',         nodeId: 'style_fixer'         },
  { label: 'Jury R1',             nodeId: 'r1'                  },
  { label: 'Jury R2',             nodeId: 'r2'                  },
  { label: 'Jury R3',             nodeId: 'r3'                  },
  { label: 'Jury F1',             nodeId: 'f1'                  },
  { label: 'Jury F2',             nodeId: 'f2'                  },
  { label: 'Jury F3',             nodeId: 'f3'                  },
  { label: 'Jury S1',             nodeId: 's1'                  },
  { label: 'Jury S2',             nodeId: 's2'                  },
  { label: 'Jury S3',             nodeId: 's3'                  },
  { label: 'Reflector',           nodeId: 'reflector'           },
  { label: 'Span Editor',         nodeId: 'span_editor'         },
  { label: 'Context Compressor',  nodeId: 'context_compressor'  },
  { label: 'Coherence Guard',     nodeId: 'coherence_guard'     },
]

const WEBHOOK_EVENTS = [
  'PIPELINE_DONE', 'PIPELINE_FAILED', 'SECTION_APPROVED',
  'HUMAN_REQUIRED', 'BUDGET_ALARM', 'OSCILLATION_DETECTED',
]

interface SettingsState {
  openrouterKey: string
  showKey: boolean
  modelAssignments: Record<string, string>
  defaultPreset: 'Economy' | 'Balanced' | 'Premium'
  defaultBudget: number
  defaultStyleProfile: string
  connectors: Record<string, boolean>
  webhookUrl: string
  webhookEvents: Record<string, boolean>
}

export function Settings() {
  const [form, setForm] = useState<SettingsState>({
    openrouterKey:      '',
    showKey:            false,
    modelAssignments:   { ...DEFAULT_MODEL_ASSIGNMENTS },
    defaultPreset:      'Balanced',
    defaultBudget:      50,
    defaultStyleProfile:'academic',
    connectors: {
      'Perplexity Sonar': true,
      'Tavily':           false,
      'Brave Search':     false,
      'Web Scraper':      false,
    },
    webhookUrl:    '',
    webhookEvents: Object.fromEntries(WEBHOOK_EVENTS.map((e) => [e, false])),
  })
  const [saving, setSaving] = useState(false)
  const [saved,  setSaved]  = useState(false)

  const patch = (p: Partial<SettingsState>) => setForm((prev) => ({ ...prev, ...p }))

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.put('/api/settings', {
        openrouter_api_key:   form.openrouterKey,
        model_assignments:    form.modelAssignments,
        default_preset:       form.defaultPreset,
        default_budget:       form.defaultBudget,
        default_style_profile:form.defaultStyleProfile,
        connectors:           form.connectors,
        webhook_url:          form.webhookUrl,
        webhook_events:       form.webhookEvents,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      console.error('Salvataggio impostazioni fallito:', e)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="w-full h-full overflow-y-auto bg-drs-bg">
      <div className="max-w-2xl mx-auto px-6 py-10 flex flex-col gap-10">

        {/* Page title */}
        <h1 className="text-xl font-semibold text-drs-text">Impostazioni</h1>

        {/* ── 1. API Keys ────────────────────────────────────────────── */}
        <section className="flex flex-col gap-4">
          <h2 className="text-xs text-drs-faint uppercase tracking-wider">
            Chiavi API
          </h2>
          <div className="bg-drs-s1 border border-drs-border rounded-[8px] p-4 flex flex-col gap-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-drs-muted">OpenRouter API Key</span>
              <div className="flex gap-2">
                <input
                  type={form.showKey ? 'text' : 'password'}
                  value={form.openrouterKey}
                  onChange={(e) => patch({ openrouterKey: e.target.value })}
                  placeholder="sk-or-v1-..."
                  className={
                    'flex-1 bg-drs-s2 border border-drs-border rounded-[4px] ' +
                    'px-3 py-2 text-sm text-drs-text placeholder:text-drs-faint ' +
                    'outline-none focus:border-drs-border-bright transition-colors font-mono'
                  }
                />
                <button
                  onClick={() => patch({ showKey: !form.showKey })}
                  className="px-3 py-2 rounded border border-drs-border text-drs-muted text-xs hover:text-drs-text transition-colors"
                >
                  {form.showKey ? 'Nascondi' : 'Mostra'}
                </button>
              </div>
            </label>
          </div>
        </section>

        {/* ── 2. Model Assignments ────────────────────────────────────── */}
        <section className="flex flex-col gap-4">
          <h2 className="text-xs text-drs-faint uppercase tracking-wider">
            Assegnazione Modelli
          </h2>
          <div className="bg-drs-s1 border border-drs-border rounded-[8px] overflow-hidden">
            {AGENT_ROWS.map(({ label, nodeId }, i) => (
              <div
                key={nodeId}
                className={
                  'flex items-center justify-between px-4 py-2.5 ' +
                  (i < AGENT_ROWS.length - 1 ? 'border-b border-drs-border' : '')
                }
              >
                <span className="text-sm text-drs-muted w-44 shrink-0">{label}</span>
                <select
                  value={form.modelAssignments[nodeId] ?? ''}
                  onChange={(e) =>
                    patch({
                      modelAssignments: { ...form.modelAssignments, [nodeId]: e.target.value },
                    })
                  }
                  className={
                    'bg-drs-s2 border border-drs-border rounded-[4px] ' +
                    'px-2 py-1.5 text-xs text-drs-text font-mono ' +
                    'outline-none focus:border-drs-border-bright transition-colors'
                  }
                >
                  {Object.entries(MODELS_BY_PROVIDER).map(([provider, models]) => (
                    <optgroup key={provider} label={provider}>
                      {models.map((m) => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </section>

        {/* ── 3. Default Config ─────────────────────────────────────── */}
        <section className="flex flex-col gap-4">
          <h2 className="text-xs text-drs-faint uppercase tracking-wider">
            Configurazione Default
          </h2>
          <div className="bg-drs-s1 border border-drs-border rounded-[8px] p-4 flex flex-col gap-4">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-drs-muted">Preset qualità</span>
              <select
                value={form.defaultPreset}
                onChange={(e) => patch({ defaultPreset: e.target.value as SettingsState['defaultPreset'] })}
                className="w-48 bg-drs-s2 border border-drs-border rounded-[4px] px-2 py-1.5 text-sm text-drs-text outline-none focus:border-drs-border-bright transition-colors"
              >
                <option value="Economy">Economy</option>
                <option value="Balanced">Balanced</option>
                <option value="Premium">Premium</option>
              </select>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-drs-muted">Budget default ($)</span>
              <input
                type="number"
                min={1}
                max={500}
                value={form.defaultBudget}
                onChange={(e) => patch({ defaultBudget: Number(e.target.value) })}
                className="w-32 bg-drs-s2 border border-drs-border rounded-[4px] px-3 py-1.5 text-sm text-drs-text outline-none focus:border-drs-border-bright transition-colors"
              />
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-drs-muted">Profilo di stile</span>
              <input
                type="text"
                value={form.defaultStyleProfile}
                onChange={(e) => patch({ defaultStyleProfile: e.target.value })}
                placeholder="academic"
                className="w-48 bg-drs-s2 border border-drs-border rounded-[4px] px-3 py-1.5 text-sm text-drs-text placeholder:text-drs-faint outline-none focus:border-drs-border-bright transition-colors"
              />
            </label>
          </div>
        </section>

        {/* ── 4. Connectors ─────────────────────────────────────────── */}
        <section className="flex flex-col gap-4">
          <h2 className="text-xs text-drs-faint uppercase tracking-wider">Connettori</h2>
          <div className="bg-drs-s1 border border-drs-border rounded-[8px] p-4 flex flex-col gap-3">
            {Object.keys(form.connectors).map((name) => (
              <label key={name} className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.connectors[name]}
                  onChange={(e) =>
                    patch({ connectors: { ...form.connectors, [name]: e.target.checked } })
                  }
                  className="w-4 h-4 accent-drs-accent"
                />
                <span className="text-sm text-drs-muted">{name}</span>
              </label>
            ))}
          </div>
        </section>

        {/* ── 5. Webhooks ───────────────────────────────────────────── */}
        <section className="flex flex-col gap-4">
          <h2 className="text-xs text-drs-faint uppercase tracking-wider">Webhook</h2>
          <div className="bg-drs-s1 border border-drs-border rounded-[8px] p-4 flex flex-col gap-4">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-drs-muted">URL</span>
              <input
                type="url"
                value={form.webhookUrl}
                onChange={(e) => patch({ webhookUrl: e.target.value })}
                placeholder="https://..."
                className={
                  'bg-drs-s2 border border-drs-border rounded-[4px] ' +
                  'px-3 py-1.5 text-sm text-drs-text placeholder:text-drs-faint ' +
                  'outline-none focus:border-drs-border-bright transition-colors'
                }
              />
            </label>

            <div className="flex flex-col gap-2">
              <span className="text-xs text-drs-muted">Eventi</span>
              <div className="grid grid-cols-2 gap-2">
                {WEBHOOK_EVENTS.map((event) => (
                  <label key={event} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={form.webhookEvents[event] ?? false}
                      onChange={(e) =>
                        patch({
                          webhookEvents: { ...form.webhookEvents, [event]: e.target.checked },
                        })
                      }
                      className="w-3.5 h-3.5 accent-drs-accent"
                    />
                    <span className="text-xs text-drs-muted font-mono">{event}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Save button */}
        <div className="flex items-center gap-3 pb-6">
          <button
            onClick={() => void handleSave()}
            disabled={saving}
            className={
              'px-5 py-2 rounded text-sm font-medium transition-all ' +
              (saving
                ? 'bg-drs-s3 text-drs-faint cursor-not-allowed'
                : 'bg-drs-accent text-white hover:opacity-90 cursor-pointer')
            }
          >
            {saving ? 'Salvataggio...' : 'Salva impostazioni'}
          </button>
          {saved && (
            <span className="text-xs text-drs-green">✓ Salvato</span>
          )}
        </div>

      </div>
    </div>
  )
}
