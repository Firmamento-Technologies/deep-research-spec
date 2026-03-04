// AppShell — the root layout component. Always rendered, survives route changes.
// Structure:
//   Topbar (fixed top, h-12)
//   Sidebar + MainArea + RightPanel (flex-1, overflow-hidden)
//   ChatInput (fixed bottom, h-20) — ALWAYS MOUNTED, NEVER UNMOUNTED
//
// useRunStream replaces useSSE as the primary stream hook.
// RunStreamContext exposes stream state to all child components.

import { createContext, useContext, useMemo } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { useRunStream } from '../../hooks/useRunStream'
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts'
import { Topbar } from './Topbar'
import { DocumentSidebar } from './DocumentSidebar'
import { MainArea } from './MainArea'
import { ChatInput } from './ChatInput'
import type { UseRunStreamResult } from '../../hooks/useRunStream'

// ── Context ────────────────────────────────────────────────────────────────
// Lets PipelineTimeline, RunCompanion and other deep children read stream
// state without prop drilling.
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

  // Stream is active during pipeline execution and HITL pauses.
  // Passing null when idle prevents EventSource from opening.
  const streamDocId =
    appState === 'PROCESSING' || appState === 'AWAITING_HUMAN' ? activeDocId : null

  const stream = useRunStream(streamDocId)

  // Global keyboard shortcuts (K, [, ])
  useKeyboardShortcuts()

  const contextValue = useMemo(() => stream, [
    stream.connected,
    stream.activeAgent,
    stream.activePhase,
    stream.activityLog,
    stream.lastEvent,
  ])

  return (
    <RunStreamContext.Provider value={contextValue}>
      <div className="flex flex-col h-screen bg-drs-bg text-drs-text">
        {/* Fixed top bar — h-12 */}
        <Topbar />

        {/* Content area — fills remaining height between topbar and chat input */}
        <div className="flex flex-1 overflow-hidden pt-12 pb-20">
          <DocumentSidebar />
          <MainArea />
          {/* RightPanel (RunCompanion) added in T4 */}
        </div>

        {/* CRITICAL: ChatInput is always mounted and always visible */}
        <ChatInput />
      </div>
    </RunStreamContext.Provider>
  )
}
