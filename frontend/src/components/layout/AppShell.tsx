// AppShell — the root layout component. Always rendered, survives route changes.
// Structure per UI_BUILD_PLAN.md Section 2:
//   Topbar (fixed top, h-12)
//   Sidebar + MainArea + RightPanel (flex-1, overflow-hidden)
//   ChatInput (fixed bottom, h-20) — ALWAYS MOUNTED, NEVER UNMOUNTED
//
// useSSE is mounted here when appState === PROCESSING | AWAITING_HUMAN.

import { useAppStore } from '../../store/useAppStore'
import { useSSE } from '../../hooks/useSSE'
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts'
import { Topbar } from './Topbar'
import { DocumentSidebar } from './DocumentSidebar'
import { MainArea } from './MainArea'
import { RightPanel } from './RightPanel'
import { ChatInput } from './ChatInput'
import { HumanRequiredModal } from '../hitl/HumanRequiredModal'

export function AppShell() {
  const appState    = useAppStore((s) => s.state)
  const activeDocId = useAppStore((s) => s.activeDocId)

  // SSE active during pipeline execution and HITL pauses
  const sseDocId =
    appState === 'PROCESSING' || appState === 'AWAITING_HUMAN' ? activeDocId : null
  useSSE(sseDocId)

  // Global keyboard shortcuts (K, [, ])
  useKeyboardShortcuts()

  return (
    <div className="flex flex-col h-screen bg-drs-bg text-drs-text">
      {/* Fixed top bar — h-12 */}
      <Topbar />

      {/* Content area — fills remaining height between topbar and chat input */}
      <div className="flex flex-1 overflow-hidden pt-12 pb-20">
        <DocumentSidebar />
        <MainArea />
        <RightPanel />
      </div>

      {/* CRITICAL: ChatInput is always mounted and always visible (Section 16 note 3) */}
      <ChatInput />

      {/*
        HITL overlay — position:fixed full-screen, NOT dismissible by clicking
        outside or pressing Escape. Renders only when appState === AWAITING_HUMAN.
        Must be outside the scrollable content area so it covers everything.
      */}
      <HumanRequiredModal />
    </div>
  )
}
