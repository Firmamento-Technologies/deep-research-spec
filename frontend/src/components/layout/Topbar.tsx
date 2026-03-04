// Topbar — fixed top, h-12.
// Left:   Logo ◈ DRS + pulsante Nuova ricerca (fuori run)
// Center: Active model badge
// Right:  Shortcut hint (durante run) + status dot + settings

import { useNavigate } from 'react-router-dom'
import { ModelBadge } from '../ui/ModelBadge'
import { useAppStore, type AppState } from '../../store/useAppStore'

const RUN_STATES: AppState[] = ['PROCESSING', 'AWAITING_HUMAN']

export function Topbar() {
  const navigate    = useNavigate()
  const appState    = useAppStore((s) => s.state)
  const openWizard  = useAppStore((s) => s.openWizard)
  const isOnline    = appState !== 'IDLE'
  const isRunning   = RUN_STATES.includes(appState)

  return (
    <header
      className={
        'fixed top-0 left-0 right-0 z-40 h-12 ' +
        'bg-drs-s1 border-b border-drs-border ' +
        'flex items-center px-4 gap-3'
      }
    >
      {/* Logo */}
      <span className="text-drs-accent font-mono text-sm font-semibold tracking-tight select-none shrink-0">
        ◈ DRS
      </span>

      {/* Pulsante Nuova ricerca — visibile solo fuori dal run */}
      {!isRunning && (
        <button
          onClick={openWizard}
          title="Nuova ricerca (N)"
          className={
            'shrink-0 flex items-center gap-1.5 ' +
            'px-2.5 py-1 rounded ' +
            'bg-drs-s2 border border-drs-border ' +
            'text-drs-muted text-xs font-mono ' +
            'hover:border-drs-accent hover:text-drs-accent transition-colors'
          }
        >
          + ricerca
          <kbd className="text-drs-faint border border-drs-border rounded px-1 py-0 text-[10px] leading-tight">
            N
          </kbd>
        </button>
      )}

      {/* Badge run attivo durante PROCESSING */}
      {isRunning && (
        <div
          className="flex items-center gap-1.5 px-2 py-1 rounded bg-drs-s2 border border-drs-border"
          title="K — toggle vista"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-drs-accent animate-dot-pulse shrink-0" />
          <span className="text-xs font-mono text-drs-accent">
            {appState === 'AWAITING_HUMAN' ? 'in attesa' : 'in esecuzione'}
          </span>
          <kbd className="text-drs-faint border border-drs-border rounded px-1 py-0 text-[10px] leading-tight ml-1">
            K
          </kbd>
        </div>
      )}

      {/* Center: companion model badge */}
      <div className="flex-1 flex justify-center">
        <ModelBadge
          model="anthropic/claude-sonnet-4-6"
          onClick={() => { /* model change dropdown — wired in STEP 5 */ }}
        />
      </div>

      {/* Right: status + settings */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-1.5" title={isOnline ? 'Online' : 'Offline'}>
          <span
            className={`w-2 h-2 rounded-full ${
              isOnline ? 'bg-drs-green' : 'bg-drs-red'
            }`}
          />
          <span className="text-xs text-drs-faint hidden md:block">
            {isOnline ? 'Online' : 'Offline'}
          </span>
        </div>

        <button
          onClick={() => navigate('/settings')}
          className={
            'w-8 h-8 flex items-center justify-center rounded ' +
            'text-drs-muted hover:text-drs-text hover:bg-drs-s2 ' +
            'transition-colors text-base'
          }
          aria-label="Impostazioni"
        >
          ⚙
        </button>
      </div>
    </header>
  )
}
