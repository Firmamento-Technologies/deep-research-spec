// Topbar — fixed top, h-12.
// Left:   Logo ◈ DRS (accent colour)
// Center: Active model badge (companion model, clickable)
// Right:  System status dot + Settings icon ⚙
// Spec: UI_BUILD_PLAN.md Section 2.

import { useNavigate } from 'react-router-dom'
import { ModelBadge } from '../ui/ModelBadge'
import { useAppStore } from '../../store/useAppStore'

export function Topbar() {
  const navigate   = useNavigate()
  const appState   = useAppStore((s) => s.state)
  const isOnline   = appState !== 'IDLE'   // simplification — health-check added in STEP 5

  return (
    <header
      className={
        'fixed top-0 left-0 right-0 z-40 h-12 ' +
        'bg-drs-s1 border-b border-drs-border ' +
        'flex items-center px-4 gap-4'
      }
    >
      {/* Left: logo */}
      <span className="text-drs-accent font-mono text-sm font-semibold tracking-tight select-none shrink-0">
        ◈ DRS
      </span>

      {/* Center: companion model badge */}
      <div className="flex-1 flex justify-center">
        <ModelBadge
          model="anthropic/claude-sonnet-4-6"
          onClick={() => { /* model change dropdown — wired in STEP 5 */ }}
        />
      </div>

      {/* Right: status dot + settings */}
      <div className="flex items-center gap-3 shrink-0">
        {/* System status dot */}
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

        {/* Settings icon */}
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
