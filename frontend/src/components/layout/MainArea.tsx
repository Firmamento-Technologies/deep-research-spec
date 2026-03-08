import { Routes, Route } from 'react-router-dom'
import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'
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

function HomeView() {
  const appState = useAppStore((s) => s.state)
  const setState = useAppStore((s) => s.setState)
  const activeRun = useRunStore((s) => s.activeRun)

  const showPipeline = appState === 'PROCESSING' || appState === 'AWAITING_HUMAN'
  const canToggle = !!activeRun && activeRun.status !== 'completed' && activeRun.status !== 'failed'

  return (
    <div className="relative w-full h-full">
      {canToggle && (
        <button
          onClick={() => setState(showPipeline ? 'CONVERSING' : 'PROCESSING')}
          className="absolute top-3 right-3 z-30 rounded border border-drs-border bg-drs-s2 px-3 py-1 text-xs text-drs-text hover:bg-drs-s1"
        >
          {showPipeline ? 'Apri Companion' : 'Torna al Grafo'}
        </button>
      )}

      <div
        className="absolute inset-0 transition-opacity duration-200"
        style={{
          opacity: showPipeline ? 0 : 1,
          pointerEvents: showPipeline ? 'none' : 'auto',
        }}
      >
        <ChatThread />
      </div>

      <div className="absolute inset-0" style={{ visibility: showPipeline ? 'visible' : 'hidden' }}>
        <PipelineCanvas />
      </div>
    </div>
  )
}
