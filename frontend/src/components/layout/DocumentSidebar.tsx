// DocumentSidebar — fixed left, collapsible to 48px.
// Width transition: CSS transition-[width] 200ms ease.
// Spec: UI_BUILD_PLAN.md Section 5.
//
// Expanded (260px):
//   + Nuovo documento  (ghost button → dispatches message to companion)
//   ◎ In corso  — active run sections with status icons
//   ✓ Completati — completed run list
//   [⬇ Esporta tutto] (sticky bottom)
//
// Collapsed (48px): coloured dots for each doc + tooltip on hover.

import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'
import { useConversationStore } from '../../store/useConversationStore'
import { SectionItem } from './SectionItem'

export function DocumentSidebar() {
  const collapsed     = useAppStore((s) => s.sidebarCollapsed)
  const toggle        = useAppStore((s) => s.toggleSidebar)
  const activeRun     = useRunStore((s) => s.activeRun)
  const completedRuns = useRunStore((s) => s.completedRuns)
  const sendMessage   = useConversationStore((s) => s.sendMessage)
  const setState      = useAppStore((s) => s.setState)
  const appState      = useAppStore((s) => s.state)

  const handleNewDoc = () => {
    if (appState === 'IDLE') setState('CONVERSING')
    void sendMessage('Voglio creare un nuovo documento di ricerca')
  }

  return (
    <aside
      style={{ width: collapsed ? '48px' : '260px', minWidth: collapsed ? '48px' : '260px' }}
      className={
        'h-full bg-drs-s1 border-r border-drs-border flex flex-col ' +
        'overflow-hidden transition-[width] duration-200 ease-in-out shrink-0'
      }
    >
      {/* Collapse / expand toggle */}
      <button
        onClick={toggle}
        className={
          'h-10 w-full flex items-center justify-center shrink-0 ' +
          'text-drs-faint hover:text-drs-muted border-b border-drs-border ' +
          'transition-colors text-sm select-none'
        }
        aria-label={collapsed ? 'Espandi sidebar' : 'Comprimi sidebar'}
      >
        {collapsed ? '›' : '‹'}
      </button>

      {/* ── EXPANDED STATE ── */}
      {!collapsed && (
        <>
          {/* New document */}
          <button
            onClick={handleNewDoc}
            className={
              'mx-3 mt-3 mb-1 px-3 py-1.5 rounded text-left text-xs ' +
              'border border-drs-border text-drs-muted ' +
              'hover:border-drs-border-bright hover:text-drs-text transition-colors'
            }
          >
            + Nuovo documento
          </button>

          {/* Active run */}
          {activeRun && (
            <div className="px-3 pt-3 pb-1">
              <p className="text-[10px] text-drs-faint uppercase tracking-wider mb-2">
                ● In corso
              </p>
              <p className="text-xs text-drs-muted mb-1 truncate px-1">
                {activeRun.topic}
              </p>
              <div className="flex flex-col">
                {activeRun.sections.map((section) => (
                  <SectionItem
                    key={section.idx}
                    section={section}
                    isRunning={section.idx === activeRun.currentSection && activeRun.status === 'running'}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Completed runs */}
          {completedRuns.length > 0 && (
            <div className="px-3 pt-3 pb-1 flex-1 overflow-y-auto min-h-0">
              <p className="text-[10px] text-drs-faint uppercase tracking-wider mb-2">
                ✓ Completati
              </p>
              {completedRuns.map((run) => (
                <button
                  key={run.docId}
                  className={
                    'w-full text-left px-2 py-1.5 rounded text-xs ' +
                    'text-drs-muted hover:text-drs-text hover:bg-drs-s2 ' +
                    'transition-colors truncate block'
                  }
                >
                  ▸ {run.topic}
                </button>
              ))}
            </div>
          )}

          {/* Export all — sticky bottom */}
          <div className="mt-auto border-t border-drs-border p-3">
            <button className="w-full text-left text-xs text-drs-faint hover:text-drs-muted transition-colors">
              ⬇ Esporta tutto
            </button>
          </div>
        </>
      )}

      {/* ── COLLAPSED STATE: coloured dots ── */}
      {collapsed && (
        <div className="flex flex-col items-center gap-2.5 mt-3 overflow-y-auto">
          {activeRun && (
            <span
              className="w-2 h-2 rounded-full bg-drs-accent animate-dot-pulse"
              title={activeRun.topic}
            />
          )}
          {completedRuns.map((run) => (
            <span
              key={run.docId}
              className="w-2 h-2 rounded-full bg-drs-green opacity-50"
              title={run.topic}
            />
          ))}
        </div>
      )}
    </aside>
  )
}
