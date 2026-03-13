// Topbar — fixed top, h-12.
// Left:   Logo + Navigation links
// Right:  System status dot + Settings icon

import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/new-research', label: 'Nuova Ricerca' },
  { to: '/spaces', label: 'Spaces' },
  { to: '/analytics', label: 'Analytics' },
]

export function Topbar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [isOnline, setIsOnline] = useState(false)

  const isSettings = location.pathname === '/settings'

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
      {/* Left: logo */}
      <button
        onClick={() => navigate('/dashboard')}
        className="text-drs-accent font-mono text-sm font-semibold tracking-tight select-none shrink-0 hover:opacity-80 transition-opacity cursor-pointer bg-transparent border-none"
      >
        ◈ DRS
      </button>

      {/* Hamburger button — mobile only */}
      <button
        className="sm:hidden flex items-center justify-center w-8 h-8 rounded text-drs-muted hover:text-drs-text hover:bg-drs-s2 transition-colors bg-transparent border-none text-base cursor-pointer"
        aria-label="Menu"
      >
        ☰
      </button>

      {/* Navigation links — hidden on mobile */}
      <nav className="hidden sm:flex items-center gap-1 ml-2">
        {NAV_ITEMS.map((item) => {
          const isActive = location.pathname === item.to ||
            (item.to !== '/dashboard' && location.pathname.startsWith(item.to))
          return (
            <Link
              key={item.to}
              to={item.to}
              className={
                'px-3 py-1.5 rounded text-xs font-medium transition-colors ' +
                (isActive
                  ? 'bg-drs-accent/15 text-drs-accent'
                  : 'text-drs-muted hover:text-drs-text hover:bg-drs-s2')
              }
            >
              {item.label}
            </Link>
          )
        })}
      </nav>

      <div className="flex-1" />

      {/* Right: status dot + settings */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-1.5" title={isOnline ? 'Online' : 'Offline'}>
          <span
            className={`w-2 h-2 rounded-full ${isOnline ? 'bg-drs-green' : 'bg-drs-red'}`}
          />
          <span className="text-xs text-drs-faint hidden md:block">
            {isOnline ? 'Online' : 'Offline'}
          </span>
        </div>

        <button
          onClick={() => navigate(isSettings ? '/dashboard' : '/settings')}
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
