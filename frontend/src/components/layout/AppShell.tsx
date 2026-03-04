// AppShell — root layout component. Always rendered, survives route changes.
// Structure:
//   Topbar (fixed top, h-12)
//   Sidebar + MainArea + RightPanel (flex-1, overflow-hidden)
//   ChatInput (fixed bottom, h-20) — ALWAYS MOUNTED, NEVER UNMOUNTED
//
// Mounts:
//   useRunStream  — stream SSE attivo durante PROCESSING / AWAITING_HUMAN
//   RunWizard     — modal, visibile quando wizardOpen === true
//   RunStreamContext — espone stream state a tutti i componenti figli

import { createContext, useContext, useMemo } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { useRunStream } from '../../hooks/useRunStream'
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts'
import { Topbar } from './Topbar'
import { DocumentSidebar } from './DocumentSidebar'
import { MainArea } from './MainArea'
import { ChatInput } from './ChatInput'
import { RunWizard } from '../wizard/RunWizard'
import type { UseRunStreamResult } from '../../hooks/useRunStream'

// ── RunStreamContext ───────────────────────────────────────────────────────────
// Espone i dati dello stream a PipelineTimeline, RunCompanion e altri
// componenti profondi, senza prop drilling.
const RunStreamContext = createContext<UseRunStreamResult>({
  connected:   false,
  activeAgent: null,
  activePhase: 'idle',
  activityLog: [],
  lastEvent:   null,
})

export function useRunStreamContext(): UseRunStreamResult {
  return useContext(RunStreamContext)
}

// ── AppShell ───────────────────────────────────────────────────────────────
export function AppShell() {
  const appState    = useAppStore((s) => s.state)
  const activeDocId = useAppStore((s) => s.activeDocId)

  // Stream aperto solo durante esecuzione e pause HITL
  const streamDocId =
    appState === 'PROCESSING' || appState === 'AWAITING_HUMAN' ? activeDocId : null

  const stream = useRunStream(streamDocId)

  useKeyboardShortcuts()

  // Stabilizza il context value per evitare re-render non necessari
  const contextValue = useMemo(
    () => stream,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [stream.connected, stream.activeAgent, stream.activePhase, stream.activityLog, stream.lastEvent],
  )

  return (
    <RunStreamContext.Provider value={contextValue}>
      <div className="flex flex-col h-screen bg-drs-bg text-drs-text">
        {/* Barra superiore fissa — h-12 */}
        <Topbar />

        {/* Area contenuto — occupa l'altezza tra topbar e chat input */}
        <div className="flex flex-1 overflow-hidden pt-12 pb-20">
          <DocumentSidebar />
          <MainArea />
          {/* RunCompanion (pannello destro) aggiunto in T4 */}
        </div>

        {/* CRITICO: ChatInput sempre montato e visibile */}
        <ChatInput />

        {/* RunWizard — modal overlay, visibile quando wizardOpen === true */}
        <RunWizard />
      </div>
    </RunStreamContext.Provider>
  )
}
