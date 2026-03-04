// RunWizard — modal multi-step per configurare e avviare un nuovo run DRS.
//
// Step 1: Topic
// Step 2: Budget ($1-$500) + Lunghezza (1k-50k parole)
//         Quality preset auto-derivato dal budget (non esposto all'utente)
// Step 3: Opzioni facoltative (lingua, stile, fonti)
//
// Submit → POST /api/runs → setActiveRun → setState PROCESSING.
// Il wizard si chiude e il run stream si attiva automaticamente (AppShell).
//
// Tastiera: N apre il wizard (via useKeyboardShortcuts).

import { useState, useCallback, type ChangeEvent } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'
import { api } from '../../lib/api'
import type { RunCreateRequest, RunCreateResponse } from '../../types/api'
import type { QualityPreset } from '../../types/run'

// ── Costanti dominio ───────────────────────────────────────────────────
const BUDGET_MIN = 1
const BUDGET_MAX = 500
const WORDS_MIN  = 1_000
const WORDS_MAX  = 50_000

const STYLE_OPTIONS = [
  { value: 'academic',     label: 'Accademico' },
  { value: 'business',     label: 'Business / Report' },
  { value: 'technical',    label: 'Tecnico' },
  { value: 'blog',         label: 'Blog / Divulgativo' },
  { value: 'journalistic', label: 'Giornalistico' },
]

const LANGUAGE_OPTIONS = [
  { value: 'it', label: 'Italiano' },
  { value: 'en', label: 'English' },
  { value: 'fr', label: 'Français' },
  { value: 'de', label: 'Deutsch' },
  { value: 'es', label: 'Español' },
]

const SOURCE_OPTIONS = [
  { value: 'web',        label: 'Web generico' },
  { value: 'academic',   label: 'Accademiche (CrossRef, Semantic Scholar)' },
  { value: 'news',       label: 'News recenti' },
  { value: 'government', label: 'Fonti istituzionali' },
  { value: 'patents',    label: 'Brevetti' },
]

// ── Quality preset ──────────────────────────────────────────────────────
function derivePreset(budget: number): QualityPreset {
  if (budget < 30)  return 'Economy'
  if (budget < 120) return 'Balanced'
  return 'Premium'
}

const PRESET_BORDER: Record<QualityPreset, string> = {
  Economy:  'border-drs-yellow  text-drs-yellow',
  Balanced: 'border-drs-accent  text-drs-accent',
  Premium:  'border-drs-green   text-drs-green',
}

const PRESET_DESC: Record<QualityPreset, string> = {
  Economy:  '3 giudici · 3 iterazioni max · ricerca base',
  Balanced: '5 giudici · 5 iterazioni · MoW attivo · ricerca avanzata',
  Premium:  '9 giudici · 8 iterazioni · MoW+Fusor · ricerca completa',
}

function estimateCost(words: number, preset: QualityPreset, maxBudget: number) {
  const low  = { Economy: 0.8, Balanced: 2.0, Premium:  5.5 }[preset]
  const high = { Economy: 1.8, Balanced: 5.0, Premium: 14.0 }[preset]
  const k    = words / 1_000
  return {
    lo: Math.min(maxBudget, +(k * low ).toFixed(1)),
    hi: Math.min(maxBudget, +(k * high).toFixed(1)),
  }
}

// ── Stili condivisi ───────────────────────────────────────────────────────
const INPUT =
  'w-full bg-drs-s2 border border-drs-border rounded-input ' +
  'px-3 py-2 text-sm text-drs-text placeholder:text-drs-faint ' +
  'outline-none focus:border-drs-border-bright transition-colors'

const LABEL = 'block text-xs font-medium text-drs-muted mb-1.5'

type Step = 1 | 2 | 3

// ── Componente ───────────────────────────────────────────────────────────
export function RunWizard() {
  const wizardOpen     = useAppStore((s) => s.wizardOpen)
  const closeWizard    = useAppStore((s) => s.closeWizard)
  const setAppState    = useAppStore((s) => s.setState)
  const setActiveDocId = useAppStore((s) => s.setActiveDocId)
  const setActiveRun   = useRunStore((s) => s.setActiveRun)

  const [step,       setStep]       = useState<Step>(1)
  const [topic,      setTopic]      = useState('')
  const [budget,     setBudget]     = useState(50)
  const [words,      setWords]      = useState(5_000)
  const [language,   setLanguage]   = useState('it')
  const [style,      setStyle]      = useState('academic')
  const [sources,    setSources]    = useState<string[]>(['web', 'academic'])
  const [submitting, setSubmitting] = useState(false)
  const [error,      setError]      = useState<string | null>(null)

  const preset = derivePreset(budget)
  const { lo, hi } = estimateCost(words, preset, budget)

  const toggleSource = useCallback((val: string) => {
    setSources((prev) =>
      prev.includes(val) ? prev.filter((s) => s !== val) : [...prev, val],
    )
  }, [])

  const resetForm = useCallback(() => {
    setStep(1); setTopic(''); setBudget(50); setWords(5_000)
    setLanguage('it'); setStyle('academic'); setSources(['web', 'academic'])
    setError(null); setSubmitting(false)
  }, [])

  const handleClose = useCallback(() => { closeWizard(); resetForm() }, [closeWizard, resetForm])
  const handleBack  = useCallback(() => {
    if (step > 1) setStep((s) => (s - 1) as Step)
    else handleClose()
  }, [step, handleClose])
  const handleNext  = useCallback(() => {
    if (step < 3) setStep((s) => (s + 1) as Step)
  }, [step])

  const handleSubmit = useCallback(async () => {
    setError(null)
    setSubmitting(true)
    try {
      const body: RunCreateRequest = {
        topic:         topic.trim(),
        qualityPreset: preset,
        targetWords:   words,
        maxBudget:     budget,
        styleProfile:  style,
      }
      const { docId } = await api.post<RunCreateResponse>('/api/runs', body)
      setActiveDocId(docId)
      setActiveRun({
        docId,
        topic:               topic.trim(),
        status:              'initializing',
        qualityPreset:       preset,
        targetWords:         words,
        maxBudget:           budget,
        budgetSpent:         0,
        // 100 per coerenza con useConversationStore (scala 0-100%)
        budgetRemainingPct:  100,
        totalSections:       0,
        currentSection:      0,
        currentIteration:    0,
        nodes:               {},
        cssScores:           { content: 0, style: 0, source: 0 },
        juryVerdicts:        [],
        sections:            [],
        shineActive:         false,
        rlmMode:             false,
        hardStopFired:       false,
        oscillationDetected: false,
        forceApprove:        false,
      })
      setAppState('PROCESSING')
      closeWizard()
      resetForm()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Errore sconosciuto')
      setSubmitting(false)
    }
  }, [topic, preset, words, budget, style,
      setActiveDocId, setActiveRun, setAppState, closeWizard, resetForm])

  if (!wizardOpen) return null

  const canNext1 = topic.trim().length >= 10

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(10,11,15,0.88)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) handleClose() }}
    >
      <div
        className="relative w-full max-w-lg bg-drs-s1 border border-drs-border rounded-card shadow-2xl"
        style={{ maxHeight: 'calc(100vh - 140px)', display: 'flex', flexDirection: 'column' }}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-6 pt-5 pb-4 border-b border-drs-border shrink-0">
          <div>
            <h2 className="text-sm font-semibold text-drs-text">Nuova ricerca</h2>
            <p className="text-xs text-drs-faint mt-0.5">
              {step === 1 && 'Passo 1 di 3 — Argomento'}
              {step === 2 && 'Passo 2 di 3 — Budget e lunghezza'}
              {step === 3 && 'Passo 3 di 3 — Opzioni'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <kbd className="text-xs font-mono text-drs-faint border border-drs-border rounded px-1 py-0.5">N</kbd>
            <button
              onClick={handleClose}
              aria-label="Chiudi wizard"
              className="text-drs-faint hover:text-drs-muted text-xl leading-none transition-colors mt-0.5"
            >
              ×
            </button>
          </div>
        </div>

        {/* Progress bar */}
        <div className="flex gap-1.5 px-6 pt-4 shrink-0">
          {([1, 2, 3] as Step[]).map((n) => (
            <div
              key={n}
              className={`h-0.5 flex-1 rounded-full transition-all duration-300 ${
                n <= step ? 'bg-drs-accent' : 'bg-drs-border'
              }`}
            />
          ))}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">

          {/* STEP 1 — Topic */}
          {step === 1 && (
            <>
              <p className="text-xs text-drs-muted leading-relaxed">
                Descrivi l&apos;argomento della ricerca. Maggiore è la precisione,
                migliore sarà la qualità dell&apos;outline generato dal Planner.
              </p>
              <div>
                <label className={LABEL}>Argomento *</label>
                <textarea
                  value={topic}
                  onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setTopic(e.target.value)}
                  placeholder="Es: Impatto dell&#39;intelligenza artificiale sull&#39;occupazione nel settore manifatturiero italiano tra il 2020 e il 2025"
                  rows={6}
                  autoFocus
                  className={INPUT + ' resize-none leading-relaxed'}
                />
                <p className="text-xs text-drs-faint mt-1.5">
                  {topic.trim().length} caratteri
                  {topic.trim().length < 10 && topic.length > 0 && (
                    <span className="text-drs-yellow ml-2">(minimo 10)</span>
                  )}
                </p>
              </div>
            </>
          )}

          {/* STEP 2 — Budget + Parole */}
          {step === 2 && (
            <div className="space-y-6">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className={LABEL.replace('mb-1.5', '')}>Budget massimo</label>
                  <span className="text-sm font-mono font-semibold text-drs-text">${budget}</span>
                </div>
                <input type="range" min={BUDGET_MIN} max={BUDGET_MAX} step={1}
                  value={budget} onChange={(e) => setBudget(Number(e.target.value))}
                  className="w-full accent-[#7C8CFF] cursor-pointer h-1.5"
                />
                <div className="flex justify-between text-xs text-drs-faint mt-1">
                  {['$1','$50','$150','$350','$500'].map((l) => <span key={l}>{l}</span>)}
                </div>
              </div>

              <div className={`border rounded-input px-3 py-2.5 flex items-center justify-between ${PRESET_BORDER[preset]}`}>
                <div>
                  <p className="text-xs font-semibold">{preset}</p>
                  <p className="text-xs opacity-60 mt-0.5">{PRESET_DESC[preset]}</p>
                </div>
                <span className="text-xs opacity-40 italic shrink-0 ml-3">automatico</span>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className={LABEL.replace('mb-1.5', '')}>Lunghezza documento</label>
                  <span className="text-sm font-mono font-semibold text-drs-text">
                    {words >= 1_000 ? `${(words / 1_000).toFixed(1).replace('.0', '')}k` : words} parole
                  </span>
                </div>
                <input type="range" min={WORDS_MIN} max={WORDS_MAX} step={500}
                  value={words} onChange={(e) => setWords(Number(e.target.value))}
                  className="w-full accent-[#7C8CFF] cursor-pointer h-1.5"
                />
                <div className="flex justify-between text-xs text-drs-faint mt-1">
                  {['1k','5k','15k','30k','50k'].map((l) => <span key={l}>{l}</span>)}
                </div>
              </div>

              <div className="bg-drs-s2 border border-drs-border rounded-input px-3 py-2.5 text-xs">
                <span className="text-drs-faint">Stima costo: </span>
                <span className="text-drs-text font-mono">${lo}–${hi}</span>
                <span className="text-drs-faint"> — calcolato esattamente dal Budget Controller all&apos;avvio</span>
              </div>
            </div>
          )}

          {/* STEP 3 — Opzioni */}
          {step === 3 && (
            <div className="space-y-5">
              <div>
                <label className={LABEL}>Lingua del documento</label>
                <select value={language} onChange={(e) => setLanguage(e.target.value)} className={INPUT}>
                  {LANGUAGE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className={LABEL}>Profilo stilistico</label>
                <div className="grid grid-cols-2 gap-2">
                  {STYLE_OPTIONS.map((o) => (
                    <button
                      key={o.value} type="button" onClick={() => setStyle(o.value)}
                      className={`px-3 py-2 rounded-input text-xs text-left transition-colors border ${
                        style === o.value
                          ? 'bg-drs-s3 border-drs-accent text-drs-accent'
                          : 'bg-drs-s2 border-drs-border text-drs-muted hover:border-drs-border-bright hover:text-drs-text'
                      }`}
                    >{o.label}</button>
                  ))}
                </div>
              </div>

              <div>
                <label className={LABEL}>Fonti da abilitare</label>
                <div className="space-y-2.5">
                  {SOURCE_OPTIONS.map((o) => (
                    <label key={o.value} className="flex items-center gap-2.5 cursor-pointer group select-none">
                      <input
                        type="checkbox" checked={sources.includes(o.value)}
                        onChange={() => toggleSource(o.value)}
                        className="accent-[#7C8CFF] w-3.5 h-3.5 cursor-pointer shrink-0"
                      />
                      <span className="text-xs text-drs-muted group-hover:text-drs-text transition-colors">
                        {o.label}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="text-xs text-drs-red bg-drs-s2 border border-drs-red rounded-input px-3 py-2">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-drs-border shrink-0">
          <button
            onClick={handleBack}
            className="px-4 py-2 text-xs text-drs-muted border border-drs-border rounded-input hover:border-drs-border-bright transition-colors"
          >
            {step === 1 ? 'Annulla' : '← Indietro'}
          </button>

          {step < 3 ? (
            <button
              onClick={handleNext}
              disabled={step === 1 && !canNext1}
              className={`px-5 py-2 text-xs rounded-input font-medium transition-all ${
                step === 1 && !canNext1
                  ? 'bg-drs-s3 text-drs-faint cursor-not-allowed'
                  : 'bg-drs-accent text-white hover:opacity-90 cursor-pointer'
              }`}
            >
              Avanti →
            </button>
          ) : (
            <button
              onClick={() => void handleSubmit()}
              disabled={submitting}
              className={`px-5 py-2 text-xs rounded-input font-medium transition-all ${
                submitting
                  ? 'bg-drs-s3 text-drs-faint cursor-not-allowed'
                  : 'bg-drs-green text-white hover:opacity-90 cursor-pointer'
              }`}
            >
              {submitting ? 'Avvio in corso…' : '⚡ Avvia ricerca'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
