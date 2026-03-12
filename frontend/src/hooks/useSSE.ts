// useSSE — connects to GET /api/runs/:docId/events and dispatches to stores.
// Mounted in AppShell when appState === 'PROCESSING'.
// Spec: UI_BUILD_PLAN.md Section 4.
//
// MOCK MODE: set VITE_MOCK_SSE=true in .env.local to replay a scripted
// event sequence for local development without a running backend.

import { useEffect, useRef, useState, useCallback } from 'react'
import { useAppStore } from '../store/useAppStore'
import { useRunStore } from '../store/useRunStore'
import type { SSEEvent } from '../types/api'

const BASE_BACKOFF = 1_000    // ms
const MAX_BACKOFF  = 30_000   // ms

export interface UseSSEResult {
  connected: boolean
  lastEvent: SSEEvent | null
}

export function useSSE(docId: string | null): UseSSEResult {
  const [connected, setConnected]   = useState(false)
  const [lastEvent, setLastEvent]   = useState<SSEEvent | null>(null)
  const esRef      = useRef<EventSource | null>(null)
  const backoff    = useRef(BASE_BACKOFF)
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Store selectors — stable references
  const appSetState  = useAppStore((s) => s.setState)
  const openHitl     = useAppStore((s) => s.openHitl)
  const updateNode   = useRunStore((s) => s.updateNode)
  const updateBudget = useRunStore((s) => s.updateBudget)
  const updateCSS    = useRunStore((s) => s.updateCSS)
  const approveSection   = useRunStore((s) => s.approveSection)
  const setOscillation   = useRunStore((s) => s.setOscillation)
  const setRunStatus     = useRunStore((s) => s.setRunStatus)
  const appendDraftChunk = useRunStore((s) => s.appendDraftChunk)
  const setHardStop      = useRunStore((s) => s.setHardStop)

  const dispatch = useCallback((raw: string) => {
    let parsed: SSEEvent
    try { parsed = JSON.parse(raw) } catch { return }
    setLastEvent(parsed)

    const { event, data } = parsed
    const now = new Date()

    switch (event) {
      case 'NODE_STARTED':
        updateNode(data.node as string, { status: 'running', startedAt: now })
        break

      case 'NODE_COMPLETED':
        updateNode(data.node as string, {
          status: 'completed',
          completedAt: now,
          durationMs: (data.duration_s as number) * 1_000,
          output: data.output,
          tokensIn:  data.tokens_in  as number | undefined,
          tokensOut: data.tokens_out as number | undefined,
          costUsd:   data.cost_usd   as number | undefined,
        })
        break

      case 'NODE_FAILED':
        updateNode(data.node as string, { status: 'failed', error: data.error as string })
        break

      case 'SECTION_APPROVED':
        approveSection(data.section_idx as number)
        break

      case 'CSS_UPDATE':
        updateCSS({
          content: data.content as number,
          style:   data.style   as number,
          source:  data.source  as number,
        })
        break

      case 'BUDGET_UPDATE':
        updateBudget(data.spent as number, data.remaining_pct as number)
        break

      case 'HUMAN_REQUIRED':
        appSetState('AWAITING_HUMAN')
        openHitl(
          data.type as 'outline_approval' | 'section_approval' | 'escalation',
          data.payload,
        )
        break

      case 'OSCILLATION_DETECTED':
        setOscillation(true, data.type as string)
        break

      case 'HARD_STOP':
        setHardStop(true)
        break

      case 'DRAFT_CHUNK':
        appendDraftChunk(data.chunk as string)
        break


      case 'RUN_RESUMED':
        appSetState('PROCESSING')
        break

      case 'PIPELINE_DONE':
        setRunStatus('completed')
        appSetState('REVIEWING')
        break

      case 'PIPELINE_FAILED':
        setRunStatus('failed')
        break
    }
  }, [
    appSetState, openHitl, updateNode, updateBudget, updateCSS,
    approveSection, setOscillation, setRunStatus, appendDraftChunk, setHardStop,
  ])

  // Real EventSource connection with exponential-backoff reconnect
  const connect = useCallback(() => {
    if (!docId) return
    const es = new EventSource(`/api/runs/${docId}/events`)
    esRef.current = es

    es.onopen = () => {
      setConnected(true)
      backoff.current = BASE_BACKOFF
    }

    es.onmessage = (e: MessageEvent<string>) => dispatch(e.data)

    es.onerror = () => {
      setConnected(false)
      es.close()
      esRef.current = null
      const delay = backoff.current
      backoff.current = Math.min(backoff.current * 2, MAX_BACKOFF)
      retryTimer.current = setTimeout(connect, delay)
    }
  }, [docId, dispatch])

  // Mock event replay for local development
  const connectMock = useCallback(() => {
    if (!docId) return
    setConnected(true)
    const MOCK_SEQUENCE: Array<[number, string, Record<string, unknown>]> = [
      [300,  'NODE_STARTED',    { node: 'preflight' }],
      [900,  'NODE_COMPLETED',  { node: 'preflight',  duration_s: 0.6 }],
      [1000, 'NODE_STARTED',    { node: 'planner' }],
      [2500, 'NODE_COMPLETED',  { node: 'planner',    duration_s: 1.5 }],
      [2600, 'HUMAN_REQUIRED',  { type: 'outline_approval', payload: { sections: [] } }],
    ]
    const timers: ReturnType<typeof setTimeout>[] = []
    for (const [delay, event, data] of MOCK_SEQUENCE) {
      timers.push(
        setTimeout(() => {
          dispatch(JSON.stringify({ event, data: { ...data, ts: new Date().toISOString() } }))
        }, delay),
      )
    }
    return () => timers.forEach(clearTimeout)
  }, [docId, dispatch])

  useEffect(() => {
    if (!docId) return
    const isMock = import.meta.env.VITE_MOCK_SSE === 'true'
    if (isMock) {
      const cleanup = connectMock()
      return cleanup
    }
    connect()
    return () => {
      esRef.current?.close()
      if (retryTimer.current) clearTimeout(retryTimer.current)
    }
  }, [docId, connect, connectMock])

  return { connected, lastEvent }
}
