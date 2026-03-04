// useRunStream — enhanced SSE hook for real-time pipeline visibility.
//
// Improvements over the original useSSE:
//   1. Connects to /api/runs/:docId/stream (spec §API)
//   2. Handles new events: AGENT_THINKING, SECTION_STARTED,
//      JURY_VERDICT, REFLECTOR_FEEDBACK
//   3. Maintains a local activityLog (max 120 entries) for PipelineTimeline
//   4. Exposes activeAgent and activePhase as derived state
//   5. Uses a phase ref to avoid EventSource reconnects on phase changes
//
// Usage: mount in AppShell when appState === 'PROCESSING' | 'AWAITING_HUMAN'.

import { useEffect, useRef, useState, useCallback } from 'react'
import { useAppStore } from '../store/useAppStore'
import { useRunStore } from '../store/useRunStore'
import type { StreamEvent, ActivityEntry, RunPhase } from '../types/stream'
import { NODE_PHASE_MAP } from '../types/stream'

const BASE_BACKOFF = 1_000   // ms
const MAX_BACKOFF  = 32_000  // ms
const MAX_LOG      = 120     // keep last N entries in memory

export interface UseRunStreamResult {
  connected:   boolean
  activeAgent: string | null
  activePhase: RunPhase
  activityLog: ActivityEntry[]
  lastEvent:   StreamEvent | null
}

export function useRunStream(docId: string | null): UseRunStreamResult {
  const [connected,   setConnected]   = useState(false)
  const [activeAgent, setActiveAgent] = useState<string | null>(null)
  const [activePhase, setActivePhase] = useState<RunPhase>('idle')
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([])
  const [lastEvent,   setLastEvent]   = useState<StreamEvent | null>(null)

  // Ref keeps the current phase available in callbacks without causing
  // EventSource reconnects (avoids putting activePhase in dep arrays).
  const phaseRef = useRef<RunPhase>('idle')

  const esRef      = useRef<EventSource | null>(null)
  const backoff    = useRef(BASE_BACKOFF)
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Store selectors (stable references) ──────────────────────────────
  const appSetState      = useAppStore((s) => s.setState)
  const openHitl         = useAppStore((s) => s.openHitl)
  const updateNode       = useRunStore((s) => s.updateNode)
  const updateBudget     = useRunStore((s) => s.updateBudget)
  const updateCSS        = useRunStore((s) => s.updateCSS)
  const approveSection   = useRunStore((s) => s.approveSection)
  const setOscillation   = useRunStore((s) => s.setOscillation)
  const setRunStatus     = useRunStore((s) => s.setRunStatus)
  const appendDraftChunk = useRunStore((s) => s.appendDraftChunk)
  const setHardStop      = useRunStore((s) => s.setHardStop)

  // ── Helpers ───────────────────────────────────────────────────────────
  const setPhase = useCallback((phase: RunPhase) => {
    phaseRef.current = phase
    setActivePhase(phase)
  }, [])

  const pushLog = useCallback((entry: Omit<ActivityEntry, 'id' | 'ts'>) => {
    const full: ActivityEntry = {
      ...entry,
      id: crypto.randomUUID(),
      ts: new Date(),
    }
    setActivityLog((prev) => [full, ...prev].slice(0, MAX_LOG))
  }, [])

  // ── Event dispatcher ──────────────────────────────────────────────────
  const dispatch = useCallback((raw: string) => {
    let parsed: StreamEvent
    try { parsed = JSON.parse(raw) } catch { return }
    setLastEvent(parsed)

    const { event, data } = parsed
    const now = new Date()

    switch (event) {

      // ── Node lifecycle ──────────────────────────────────────────────
      case 'NODE_STARTED': {
        const node  = data.node as string
        const phase = NODE_PHASE_MAP[node] ?? 'idle'
        updateNode(node, { status: 'running', startedAt: now })
        setActiveAgent(node)
        setPhase(phase)
        pushLog({ type: 'node_started', label: `Avvio: ${node}`, node, phase })
        break
      }

      case 'NODE_COMPLETED': {
        const node = data.node as string
        updateNode(node, {
          status:      'completed',
          completedAt: now,
          durationMs:  (data.duration_s as number) * 1_000,
          output:      data.output,
          tokensIn:    data.tokens_in  as number | undefined,
          tokensOut:   data.tokens_out as number | undefined,
          costUsd:     data.cost_usd   as number | undefined,
          model:       data.model      as string | undefined,
        })
        setActiveAgent(null)
        pushLog({
          type:  'node_completed',
          label: `Completato: ${node}`,
          node,
          phase: NODE_PHASE_MAP[node] ?? 'idle',
          meta:  {
            durationMs: (data.duration_s as number) * 1_000,
            costUsd:    data.cost_usd as number | undefined,
            model:      data.model    as string | undefined,
          },
        })
        break
      }

      case 'NODE_FAILED': {
        const node = data.node as string
        updateNode(node, { status: 'failed', error: data.error as string })
        pushLog({
          type:  'error',
          label: `Errore in ${node}: ${data.error ?? 'errore sconosciuto'}`,
          node,
          phase: NODE_PHASE_MAP[node] ?? phaseRef.current,
        })
        break
      }

      // ── Agent thinking (intermediate thought, before output) ────────
      case 'AGENT_THINKING': {
        const node    = data.node    as string
        const summary = data.summary as string | undefined
        pushLog({
          type:  'thinking',
          label: summary ?? `${node} sta elaborando…`,
          node,
          phase: NODE_PHASE_MAP[node] ?? phaseRef.current,
        })
        break
      }

      // ── Section lifecycle ───────────────────────────────────────────
      case 'SECTION_STARTED': {
        const idx   = data.section_idx as number
        const title = data.title       as string
        setPhase('writing')
        pushLog({
          type:  'section_started',
          label: `Sezione ${idx + 1}: ${title}`,
          phase: 'writing',
          meta:  { sectionIdx: idx, sectionTitle: title },
        })
        break
      }

      case 'SECTION_APPROVED': {
        const idx = data.section_idx as number
        approveSection(idx)
        pushLog({
          type:  'section_approved',
          label: `✓ Sezione ${idx + 1} approvata (CSS ${(data.css as number)?.toFixed(2) ?? '—'})`,
          phase: 'jury',
          meta:  { sectionIdx: idx, css: data.css },
        })
        break
      }

      // ── Jury verdict ────────────────────────────────────────────────
      case 'JURY_VERDICT': {
        const sectionIdx = data.section_idx as number
        const iteration  = data.iteration   as number
        const approved   = data.approved    as boolean
        const css        = data.css         as number
        pushLog({
          type:  approved ? 'jury_pass' : 'jury_fail',
          label: approved
            ? `Giuria — sez. ${sectionIdx + 1} iter. ${iteration}: approvata (CSS ${css.toFixed(2)})`
            : `Giuria — sez. ${sectionIdx + 1} iter. ${iteration}: rifiutata (CSS ${css.toFixed(2)})`,
          phase: 'jury',
          meta:  { sectionIdx, iteration, css, approved },
        })
        break
      }

      // ── Reflector feedback ──────────────────────────────────────────
      case 'REFLECTOR_FEEDBACK': {
        const scope = data.scope as string
        const count = data.count as number
        pushLog({
          type:  'reflector',
          label: `Reflector [${scope}] — ${count} istruzion${count === 1 ? 'e' : 'i'} al Writer`,
          phase: 'reflecting',
          meta:  { scope, feedbackCount: count },
        })
        break
      }

      // ── CSS / Budget ────────────────────────────────────────────────
      case 'CSS_UPDATE':
        updateCSS({
          content: data.content as number,
          style:   data.style   as number,
          source:  data.source  as number,
        })
        break

      case 'BUDGET_UPDATE':
        updateBudget(data.spent as number, data.remaining_pct as number)
        pushLog({
          type:  'budget',
          label: `Budget: $${(data.spent as number).toFixed(3)} (${Math.round((data.remaining_pct as number) * 100)}% rimanente)`,
          phase: phaseRef.current,
          meta:  { spent: data.spent, remainingPct: data.remaining_pct },
        })
        break

      // ── HITL / Oscillation / Hard stop ──────────────────────────────
      case 'HUMAN_REQUIRED':
        appSetState('AWAITING_HUMAN')
        openHitl(
          data.type as 'outline_approval' | 'section_approval' | 'escalation',
          data.payload,
        )
        pushLog({
          type:  'human_required',
          label: `Intervento richiesto: ${data.type}`,
          phase: phaseRef.current,
        })
        break

      case 'OSCILLATION_DETECTED':
        setOscillation(true, data.type as string)
        pushLog({
          type:  'warning',
          label: `Oscillazione rilevata (${data.type}) — escalation in corso`,
          phase: phaseRef.current,
        })
        break

      case 'HARD_STOP':
        setHardStop(true)
        setPhase('failed')
        pushLog({
          type:  'error',
          label: 'Hard stop — budget o iterazioni esaurite',
          phase: phaseRef.current,
        })
        break

      case 'DRAFT_CHUNK':
        appendDraftChunk(data.chunk as string)
        break

      case 'PIPELINE_DONE':
        setRunStatus('completed')
        setPhase('done')
        setActiveAgent(null)
        appSetState('REVIEWING')
        pushLog({ type: 'done', label: '✓ Pipeline completata', phase: 'done' })
        break

      case 'PIPELINE_FAILED':
        setRunStatus('failed')
        setPhase('failed')
        setActiveAgent(null)
        pushLog({
          type:  'error',
          label: `Pipeline fallita: ${(data.error as string) ?? 'errore sconosciuto'}`,
          phase: 'failed',
        })
        break
    }
  }, [
    appSetState, openHitl, updateNode, updateBudget, updateCSS,
    approveSection, setOscillation, setRunStatus, appendDraftChunk,
    setHardStop, pushLog, setPhase,
  ])

  // ── Real EventSource with exponential-backoff reconnect ──────────────
  const connect = useCallback(() => {
    if (!docId) return
    const es = new EventSource(`/api/runs/${docId}/stream`)
    esRef.current = es

    es.onopen = () => {
      setConnected(true)
      backoff.current = BASE_BACKOFF
      pushLog({ type: 'system', label: 'Stream connesso', phase: phaseRef.current })
    }

    es.onmessage = (e: MessageEvent<string>) => dispatch(e.data)

    es.onerror = () => {
      setConnected(false)
      es.close()
      esRef.current = null
      const delay = backoff.current
      backoff.current = Math.min(backoff.current * 2, MAX_BACKOFF)
      pushLog({
        type:  'system',
        label: `Connessione persa — reconnessione tra ${delay / 1000}s…`,
        phase: phaseRef.current,
      })
      retryTimer.current = setTimeout(connect, delay)
    }
  }, [docId, dispatch, pushLog])

  // ── Mock replay for local development (VITE_MOCK_SSE=true) ───────────
  const connectMock = useCallback(() => {
    if (!docId) return
    setConnected(true)
    pushLog({ type: 'system', label: 'MOCK — stream simulato attivo', phase: 'idle' })

    const SEQ: Array<[number, string, Record<string, unknown>]> = [
      [200,  'NODE_STARTED',       { node: 'preflight' }],
      [800,  'NODE_COMPLETED',     { node: 'preflight',   duration_s: 0.6 }],
      [900,  'NODE_STARTED',       { node: 'planner' }],
      [1300, 'AGENT_THINKING',     { node: 'planner', summary: 'Analisi topic e strutturazione outline…' }],
      [2500, 'NODE_COMPLETED',     { node: 'planner',     duration_s: 1.6,  model: 'google/gemini-2.5-pro' }],
      [2600, 'SECTION_STARTED',    { section_idx: 0, title: 'Introduzione' }],
      [2700, 'NODE_STARTED',       { node: 'researcher' }],
      [3100, 'AGENT_THINKING',     { node: 'researcher', summary: 'Ricerca CrossRef + Semantic Scholar…' }],
      [4000, 'NODE_COMPLETED',     { node: 'researcher',  duration_s: 1.3,  cost_usd: 0.002 }],
      [4100, 'NODE_STARTED',       { node: 'writer' }],
      [5000, 'AGENT_THINKING',     { node: 'writer', summary: 'Generazione draft sezione 1 (Coverage angle)…' }],
      [6400, 'NODE_COMPLETED',     { node: 'writer',      duration_s: 2.3,  cost_usd: 0.045, model: 'anthropic/claude-opus-4-5' }],
      [6500, 'NODE_STARTED',       { node: 'jury' }],
      [7200, 'JURY_VERDICT',       { section_idx: 0, iteration: 1, approved: false, css: 0.41 }],
      [7300, 'NODE_STARTED',       { node: 'reflector' }],
      [7900, 'REFLECTOR_FEEDBACK', { scope: 'PARTIAL', count: 3 }],
      [8000, 'NODE_COMPLETED',     { node: 'reflector',   duration_s: 0.7 }],
      [8100, 'NODE_STARTED',       { node: 'writer' }],
      [9400, 'NODE_COMPLETED',     { node: 'writer',      duration_s: 1.3,  cost_usd: 0.038 }],
      [9500, 'JURY_VERDICT',       { section_idx: 0, iteration: 2, approved: true, css: 0.72 }],
      [9600, 'SECTION_APPROVED',   { section_idx: 0, css: 0.72 }],
      [9700, 'BUDGET_UPDATE',      { spent: 0.089, remaining_pct: 0.82 }],
      [9800, 'CSS_UPDATE',         { content: 0.72, style: 0.81, source: 0.68 }],
      [9900, 'HUMAN_REQUIRED',     { type: 'outline_approval', payload: { sections: [] } }],
    ]

    const timers: ReturnType<typeof setTimeout>[] = []
    for (const [delay, event, data] of SEQ) {
      timers.push(
        setTimeout(() => {
          dispatch(JSON.stringify({ event, data: { ...data, ts: new Date().toISOString() } }))
        }, delay),
      )
    }
    return () => timers.forEach(clearTimeout)
  }, [docId, dispatch, pushLog])

  // ── Mount / unmount ──────────────────────────────────────────────────
  useEffect(() => {
    if (!docId) {
      setPhase('idle')
      setActiveAgent(null)
      setActivityLog([])
      setConnected(false)
      return
    }

    const isMock = import.meta.env.VITE_MOCK_SSE === 'true'
    if (isMock) {
      const cleanup = connectMock()
      return cleanup ?? undefined
    }

    connect()
    return () => {
      esRef.current?.close()
      if (retryTimer.current) clearTimeout(retryTimer.current)
    }
  }, [docId, connect, connectMock, setPhase])

  return { connected, activeAgent, activePhase, activityLog, lastEvent }
}
