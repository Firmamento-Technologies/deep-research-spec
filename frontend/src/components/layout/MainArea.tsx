// MainArea — area contenuto flex-1 tra sidebar e pannello destro.
// Route: / (HomeView), /settings, /analytics.
// HomeView: ChatThread ↔ PipelineTimeline in base all'appState.
// visibility:hidden (non unmount) preserva lo stato dell'activity log.

import { Routes, Route } from 'react-router-dom'
import { useAppStore } from '../../store/useAppStore'
import { ChatThread } from '../chat/ChatThread'
import { PipelineTimeline } from '../pipeline/PipelineTimeline'
import { Settings }  from '../../pages/Settings'
import { Analytics } from '../../pages/Analytics'

export function MainArea() {
  return (
    <main className="flex-1 overflow-hidden relative min-w-0">
      <Routes>
        <Route path="/"          element={<HomeView />}  />
        <Route path="/settings"  element={<Settings />}  />
        <Route path="/analytics" element={<Analytics />} />
      </Routes>
    </main>
  )
}

/** Sovrappone Chat e PipelineTimeline — una sola visibile alla volta. */
function HomeView() {
  const appState     = useAppStore((s) => s.state)
  const showTimeline = appState === 'PROCESSING' || appState === 'AWAITING_HUMAN'

  return (
    <div className="relative w-full h-full">

      {/* ── CHAT VIEW ──────────────────────────────────────────────── */}
      <div
        className="absolute inset-0 transition-opacity duration-200"
        style={{
          opacity:       showTimeline ? 0 : 1,
          pointerEvents: showTimeline ? 'none' : 'auto',
        }}
      >
        <ChatThread />
      </div>

      {/* ── PIPELINE TIMELINE ────────────────────────────────────────── */}
      {/* visibility:hidden (non unmount) mantiene activityLog e stato scroll */}
      <div
        className="absolute inset-0"
        style={{ visibility: showTimeline ? 'visible' : 'hidden' }}
      >
        <PipelineTimeline />
      </div>

    </div>
  )
}
