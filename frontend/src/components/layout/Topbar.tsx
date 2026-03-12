// Topbar — fixed top, h-12.
// Left:   Logo ◈ DRS (accent colour, links to home)
// Center: Active model badge (companion model, clickable)
// Right:  System status dot + Settings icon ⚙ (toggles to/from /settings)

import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { ModelBadge } from '../ui/ModelBadge'

export function Topbar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [isOnline, setIsOnline] = useState(false)

  const isSettings = location.pathname === '/settings'

  // Health-check polling — every 10s
  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch('/health', { method: 'GET', signal: AbortSignal.timeout(5000) })
      setIsOnline(res.ok)
    } catch {
      setIsOnline(false)
    }
  }, [])

  useEffect(() => {
    checkHealth()
    const interval = setInterval(checkHealth, 10_000)
    return () => clearInterval(interval)
  }, [checkHealth])

  return (
    <header
      className={
        'fixed top-0 left-0 right-0 z-40 h-12 ' +
        'bg-drs-s1 border-b border-drs-border ' +
        'flex items-center px-4 gap-4'
      }
    >
      {/* Left: logo — clickable, navigates to home */}
      <button
        onClick={() => navigate('/')}
        className="text-drs-accent font-mono text-sm font-semibold tracking-tight select-none shrink-0 hover:opacity-80 transition-opacity cursor-pointer bg-transparent border-none"
      >
        ◈ DRS
      </button>

      {/* Center: companion model badge */}
      <div className="flex-1 flex justify-center">
        <ModelBadge
          model="anthropic/claude-sonnet-4"
          onClick={() => { /* model change dropdown — wired in STEP 5 */ }}
        />
      </div>

      {/* Right: status dot + settings */}
      <div className="flex items-center gap-3 shrink-0">
        {/* System status dot */}
        <div className="flex items-center gap-1.5" title={isOnline ? 'Online' : 'Offline'}>
          <span
            className={`w-2 h-2 rounded-full ${isOnline ? 'bg-drs-green' : 'bg-drs-red'
              }`}
          />
          <span className="text-xs text-drs-faint hidden md:block">
            {isOnline ? 'Online' : 'Offline'}
          </span>
        </div>

        {/* Settings icon — toggles between / and /settings */}
        <button
          onClick={() => navigate(isSettings ? '/' : '/settings')}
          className={
            'w-8 h-8 flex items-center justify-center rounded ' +
            'transition-colors text-base ' +
            (isSettings
              ? 'text-drs-accent bg-drs-s2'
              : 'text-drs-muted hover:text-drs-text hover:bg-drs-s2')
          }
          aria-label={isSettings ? 'Torna alla home' : 'Impostazioni'}
          title={isSettings ? 'Torna alla home' : 'Impostazioni'}
        >
          {isSettings ? '✕' : '⚙'}
        </button>
      </div>
    </header>
  )
}
