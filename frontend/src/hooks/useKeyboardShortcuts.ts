// useKeyboardShortcuts — shortcut globali per la UI DRS.
// Montato una volta in AppShell. Ignorati quando il focus è in input/textarea.
//
// K — toggle Chat ↔ PipelineTimeline (solo con run attivo)
// [ — toggle sidebar
// ] — toggle right panel
// N — apri RunWizard (Nuova ricerca, solo in IDLE/CONVERSING/REVIEWING)
// C — toggle RunCompanion panel (solo in PROCESSING/AWAITING_HUMAN)

import { useEffect } from 'react'
import { useAppStore, type AppState } from '../store/useAppStore'

const PIPELINE_STATES: AppState[] = ['PROCESSING', 'AWAITING_HUMAN']
const CHAT_STATES:     AppState[] = ['CONVERSING', 'REVIEWING']
const NO_RUN_STATES:   AppState[] = ['IDLE', 'CONVERSING', 'REVIEWING']

export function useKeyboardShortcuts() {
  const state           = useAppStore((s) => s.state)
  const setState        = useAppStore((s) => s.setState)
  const toggleSidebar   = useAppStore((s) => s.toggleSidebar)
  const togglePanel     = useAppStore((s) => s.toggleRightPanel)
  const openWizard      = useAppStore((s) => s.openWizard)
  const toggleCompanion = useAppStore((s) => s.toggleCompanion)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Ignora quando il focus è in un campo di testo
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      // Ignora se un modificatore è premuto (Cmd/Ctrl/Alt)
      if (e.metaKey || e.ctrlKey || e.altKey) return

      switch (e.key.toLowerCase()) {
        case 'k':
          // Toggle Pipeline ↔ Chat (solo con run attivo)
          if (PIPELINE_STATES.includes(state))      setState('CONVERSING')
          else if (CHAT_STATES.includes(state))     setState('PROCESSING')
          break

        case 'n':
          // Apri wizard nuova ricerca (solo senza run attivo)
          if (NO_RUN_STATES.includes(state)) {
            e.preventDefault()
            openWizard()
          }
          break

        case 'c':
          // Toggle companion panel (solo durante run)
          if (PIPELINE_STATES.includes(state)) {
            e.preventDefault()
            toggleCompanion()
          }
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
  }, [state, setState, toggleSidebar, togglePanel, openWizard, toggleCompanion])
}
