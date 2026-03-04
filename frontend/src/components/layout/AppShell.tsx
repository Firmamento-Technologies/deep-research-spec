// AppShell — root layout component. Always rendered, survives route changes.
//
// Layout colonne (flex row, tra topbar h-12 e chat input h-20):
//   DocumentSidebar (w-sidebar | w-sidebar-sm se collassato)
//   MainArea        (flex-1)
//   Pannello destro:
//     - RightPanel    durante IDLE / CONVERSING / REVIEWING
//     - RunCompanion  durante PROCESSING / AWAITING_HUMAN
//
// Sempre montati:
//   ChatInput  (fixed bottom)  — mai smontato
//   RunWizard  (modal z-50)    — visibile quando wizardOpen
//
// RunStreamContext espone i dati SSE a tutti i figli senza prop drilling.

import { createContext, useContext, useMemo } from 'react'
import { useAppStore, type AppState } from '../../store/useAppStore'
import { useRunStream } from '../../hooks/useRunStream'
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts'
import { Topbar }          from './Topbar'
import { DocumentSidebar } from './DocumentSidebar'
import { MainArea }        from './MainArea'
import { ChatInput }       from './ChatInput'
import { RightPanel }      from './RightPanel'
import { RunWizard }       from '../wizard/RunWizard'
import { RunCompanion }    from '../companion/RunCompanion'
import type { UseRunStreamResult } from '../../hooks/useRunStream'

const RUN_STATES: AppState[] = ['PROCESSING', 'AWAITING_HUMAN']

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
  const isRunning   = RUN_STATES.includes(appState)

  // Stream aperto solo durante esecuzione e pause HITL.
  // null quando idle — evita di aprire EventSource inutilmente.
  const streamDocId = isRunning ? activeDocId : null
  const stream      = useRunStream(streamDocId)

  useKeyboardShortcuts()

  const contextValue = useMemo(
    () => stream,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [stream.connected, stream.activeAgent, stream.activePhase, stream.activityLog, stream.lastEvent],
  )

  return (
    <RunStreamContext.Provider value={contextValue}>
      <div className="flex flex-col h-screen bg-drs-bg text-drs-text">

        <Topbar />

        <div className="flex flex-1 overflow-hidden pt-12 pb-20">
          <DocumentSidebar />
          <MainArea />

          {/*
            Pannello destro:
            - Durante il run (PROCESSING / AWAITING_HUMAN): RunCompanion
            - Negli altri stati (IDLE / CONVERSING / REVIEWING): RightPanel
            Il cambio è hard (unmount/mount) così nessuno dei due
            mantiene stato stantio dell'altro.
          */}
          {isRunning
            ? <RunCompanion />
            : <RightPanel />
          }
        </div>

        {/* ChatInput — sempre montato, mai smontato */}
        <ChatInput />

        {/* RunWizard — modal overlay z-50 */}
        <RunWizard />

      </div>
    </RunStreamContext.Provider>
  )
}
