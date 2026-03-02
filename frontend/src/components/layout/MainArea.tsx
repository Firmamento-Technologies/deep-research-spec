// MainArea — the flex-1 content area between sidebar and right panel.
// Handles routing for /, /settings, /analytics.
// For the home route: switches Chat ↔ Pipeline view based on appState.
//
// CRITICAL (Section 16 note 7):
//   PipelineCanvas uses visibility:hidden — NOT unmounted — when
//   the user switches to Chat view (K shortcut). This preserves
//   animation state (running node pulse-glow, particle edges).

import { Routes, Route } from 'react-router-dom'
import { useAppStore } from '../../store/useAppStore'
import { Settings } from '../../pages/Settings'
import { Analytics } from '../../pages/Analytics'

export function MainArea() {
  return (
    <main className="flex-1 overflow-hidden relative min-w-0">
      <Routes>
        <Route path="/"          element={<HomeView />} />
        <Route path="/settings"  element={<Settings />} />
        <Route path="/analytics" element={<Analytics />} />
      </Routes>
    </main>
  )
}

// HomeView: Chat ↔ Pipeline depending on appState
function HomeView() {
  const appState = useAppStore((s) => s.state)
  const showPipeline = appState === 'PROCESSING' || appState === 'AWAITING_HUMAN'

  return (
    <div className="relative w-full h-full">
      {/* Chat view: visible for IDLE / CONVERSING / REVIEWING */}
      <div
        className="absolute inset-0 transition-opacity duration-200"
        style={{
          opacity:       showPipeline ? 0 : 1,
          pointerEvents: showPipeline ? 'none' : 'auto',
        }}
      >
        <ChatThreadPlaceholder />
      </div>

      {/* Pipeline canvas: visibility:hidden (not unmounted) to preserve state */}
      <div
        className="absolute inset-0"
        style={{ visibility: showPipeline ? 'visible' : 'hidden' }}
      >
        <PipelineCanvasPlaceholder />
      </div>
    </div>
  )
}

// ── Placeholders — replaced in STEP 6 and STEP 7 respectively ──────────────

function ChatThreadPlaceholder() {
  const appState = useAppStore((s) => s.state)

  if (appState === 'IDLE') {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center select-none">
        <p className="text-drs-accent font-mono text-3xl mb-3">◈  DRS</p>
        <p className="text-drs-muted text-sm">Cosa vuoi esplorare oggi?</p>
      </div>
    )
  }

  return (
    <div className="w-full h-full flex items-center justify-center">
      {/* ChatThread implemented in STEP 6 */}
      <p className="text-drs-faint text-xs font-mono">ChatThread — STEP 6</p>
    </div>
  )
}

function PipelineCanvasPlaceholder() {
  return (
    <div className="w-full h-full flex items-center justify-center bg-drs-bg">
      {/* PipelineCanvas implemented in STEP 7 */}
      <p className="text-drs-faint text-xs font-mono">PipelineCanvas — STEP 7</p>
    </div>
  )
}
