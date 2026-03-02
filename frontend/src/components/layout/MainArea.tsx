import { Routes, Route } from 'react-router-dom'
import { useAppStore } from '../../store/useAppStore'
import { ChatThread } from '../chat/ChatThread'
import { PipelineCanvas } from '../pipeline/PipelineCanvas'
import { Settings } from '../../pages/Settings'
import { Analytics } from '../../pages/Analytics'

export function MainArea() {
  return (
    <main className="flex-1 overflow-hidden relative min-w-0">
      <Routes>
        <Route path="/" element={<HomeView />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/analytics" element={<Analytics />} />
      </Routes>
    </main>
  )
}

/** Overlays Chat and Pipeline — only one is visible at a time. */
function HomeView() {
  const appState = useAppStore((s) => s.state)
  const showPipeline = appState === 'PROCESSING' || appState === 'AWAITING_HUMAN'

  return (
    <div className="relative w-full h-full">
      {/* ── CHAT VIEW ───────────────────────────────────────────────── */}
      <div
        className="absolute inset-0 transition-opacity duration-200"
        style={{
          opacity: showPipeline ? 0 : 1,
          pointerEvents: showPipeline ? 'none' : 'auto',
        }}
      >
        <ChatThread />
      </div>

      {/* ── PIPELINE CANVAS ──────────────────────────────────────────── */}
      {/* visibility:hidden (not unmount) preserves animation state */}
      <div
        className="absolute inset-0"
        style={{ visibility: showPipeline ? 'visible' : 'hidden' }}
      >
        <PipelineCanvas />
      </div>
    </div>
  )
}

