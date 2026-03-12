// useKeyboardShortcuts — global keyboard shortcuts for the DRS UI.
// Mount once in AppShell.
//
// K  — toggle Chat ↔ Pipeline view (Section 16, note 7)
// [  — toggle sidebar collapse
// ]  — toggle right panel collapse

import { useEffect } from 'react'
import { useAppStore, type AppState } from '../store/useAppStore'

const PIPELINE_STATES: AppState[] = ['PROCESSING', 'AWAITING_HUMAN']
const CHAT_STATES: AppState[]     = ['CONVERSING', 'REVIEWING']

export function useKeyboardShortcuts() {
  const state          = useAppStore((s) => s.state)
  const setState       = useAppStore((s) => s.setState)
  const toggleSidebar  = useAppStore((s) => s.toggleSidebar)
  const togglePanel    = useAppStore((s) => s.toggleRightPanel)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Ignore when focus is inside an input / textarea
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      switch (e.key.toLowerCase()) {
        case 'k':
          // Toggle: Pipeline ↔ Chat (only when a run is active)
          if (PIPELINE_STATES.includes(state)) setState('CONVERSING')
          else if (CHAT_STATES.includes(state))  setState('PROCESSING')
          break
        case '[':
          toggleSidebar()
          break
        case ']':
          togglePanel()
          break
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [state, setState, toggleSidebar, togglePanel])
}
