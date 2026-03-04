// AppShell — root layout component. Always rendered, survives route changes.
// Structure:
//   Topbar (fixed top, h-12)
//   DocumentSidebar + MainArea + RunCompanion (flex-1, overflow-hidden)
//   ChatInput (fixed bottom, h-20) — ALWAYS MOUNTED, NEVER UNMOUNTED
//
// Mounts:
//   useRunStream  — stream SSE durante PROCESSING / AWAITING_HUMAN
//   RunWizard     — modal, visibile quando wizardOpen === true
//   RunCompanion  — pannello destro, visibile durante PROCESSING / AWAITING_HUMAN
//   RunStreamContext — espone stream state a tutti i figli

import { createContext, useContext, useMemo } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { useRunStream } from '../../hooks/useRunStream'
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts'
import { Topbar }          from './Topbar'
import { DocumentSidebar } from './DocumentSidebar'
import { MainArea }        from './MainArea'
import { ChatInput }       from './ChatInput'
import { RunWizard }       from '../wizard/RunWizard'
import { RunCompanion }    from '../companion/RunCompanion'
import type { UseRunStreamResult } from '../../hooks/useRunStream'

// ── RunStreamContext ───────────────────────────────────────────────────────────
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
    appState === 'PROCESSING' || appState === 'AWAITING_HUMAN'
      ? activeDocId
      : null

  const stream = useRunStream(streamDocId)

  useKeyboardShortcuts()

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

        {/* Area contenuto — occupa l’altezza tra topbar e chat input */}
        <div className="flex flex-1 overflow-hidden pt-12 pb-20">
          <DocumentSidebar />
          <MainArea />
          {/* RunCompanion si auto-nasconde quando appState non è PROCESSING/AWAITING_HUMAN */}
          <RunCompanion />
        </div>

        {/* CRITICO: ChatInput sempre montato e sempre visibile */}
        <ChatInput />

        {/* RunWizard — modal overlay, z-50 */}
        <RunWizard />

      </div>
    </RunStreamContext.Provider>
  )
}
