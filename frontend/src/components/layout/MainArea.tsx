import { Outlet, useLocation } from 'react-router-dom'
import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'
import { ChatThread } from '../chat/ChatThread'
import { PipelineCanvas } from '../pipeline/PipelineCanvas'

export function MainArea() {
  const appState = useAppStore((s) => s.state)
  const setState = useAppStore((s) => s.setState)
  const activeRun = useRunStore((s) => s.activeRun)
  const location = useLocation()

  const showPipeline = appState === 'PROCESSING' || appState === 'AWAITING_HUMAN'
  const canToggle = !!activeRun && activeRun.status !== 'completed' && activeRun.status !== 'failed'
  const isDashboard = location.pathname === '/dashboard' || location.pathname === '/'

  return (
    <main className="flex-1 overflow-hidden relative min-w-0">
      {/* Page content — always rendered, hidden when pipeline is active */}
      <div
        className="absolute inset-0 overflow-auto"
        style={{
          opacity: showPipeline ? 0 : 1,
          pointerEvents: showPipeline ? 'none' : 'auto',
          transition: 'opacity 200ms',
        }}
      >
        {isDashboard ? <ChatThread /> : <Outlet />}
      </div>

      {/* Pipeline overlay — visible when a run is processing */}
      {activeRun && (
        <div
          className="absolute inset-0"
          style={{ visibility: showPipeline ? 'visible' : 'hidden' }}
        >
          <PipelineCanvas />
        </div>
      )}

      {/* Toggle button: pipeline <-> page/chat */}
      {canToggle && (
        <button
          onClick={() => setState(showPipeline ? 'CONVERSING' : 'PROCESSING')}
          className="absolute top-3 right-3 z-30 rounded border border-drs-border bg-drs-s2 px-3 py-1 text-xs text-drs-text hover:bg-drs-s1 focus:outline-none focus:ring-2 focus:ring-drs-accent"
        >
          {showPipeline ? 'Torna alla pagina' : 'Mostra Pipeline'}
        </button>
      )}

      {/* Active run indicator — shown when on a non-dashboard page with active run */}
      {!showPipeline && activeRun && !isDashboard && (
        <div className="absolute bottom-2 right-3 z-20">
          <button
            onClick={() => setState('PROCESSING')}
            className="flex items-center gap-2 rounded-lg border border-drs-accent/30 bg-drs-s1 px-3 py-2 text-xs text-drs-accent hover:bg-drs-s2 transition shadow-lg"
          >
            <span className="w-2 h-2 rounded-full bg-drs-green animate-pulse" />
            Ricerca in corso — Mostra Pipeline
          </button>
        </div>
      )}
    </main>
  )
}
