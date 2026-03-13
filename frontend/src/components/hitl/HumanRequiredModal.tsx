import { useAppStore } from '../../store/useAppStore'
import { OutlineDragList } from './OutlineDragList'
import { SectionReviewSplit } from './SectionReviewSplit'
import { EscalationBanner } from './EscalationBanner'

/**
 * HumanRequiredModal
 * Triggered when appState === 'AWAITING_HUMAN'.
 * Full-screen overlay — NOT dismissible by clicking outside or pressing Escape.
 * hitlType is read from useAppStore (set by openHitl via useSSE).
 */
export function HumanRequiredModal() {
  const { state: appState, activeDocId, hitlType } = useAppStore()

  if (appState !== 'AWAITING_HUMAN' || !activeDocId) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-[4px]"
      style={{ background: 'rgba(0,0,0,0.85)' }}
    // NOT dismissible — no onClick on overlay
    >
      <div
        className="bg-drs-s1 border border-drs-border rounded-[12px] w-[90vw] max-h-[90vh] flex flex-col overflow-hidden shadow-[0_24px_64px_rgba(0,0,0,0.7)]"
        style={{ maxWidth: hitlType === 'section_approval' ? 1100 : 680 }}
        onClick={e => e.stopPropagation()}
      >
        {/* Modal header */}
        <div className="p-[14px_20px] border-b border-drs-border flex items-center gap-[10px] shrink-0">
          <span className="w-[10px] h-[10px] rounded-full bg-drs-orange inline-block shadow-[0_0_8px_#F97316]" />
          <span className="text-[13px] font-mono text-drs-text font-bold">
            {hitlType === 'outline_approval' && 'APPROVAZIONE OUTLINE'}
            {hitlType === 'section_approval' && 'REVISIONE SEZIONE'}
            {hitlType === 'escalation' && 'ESCALATION — AZIONE RICHIESTA'}
            {!hitlType && 'AZIONE RICHIESTA'}
          </span>
          <span className="ml-auto text-[10px] font-mono text-drs-orange rounded-[3px] px-[8px] py-[2px]" style={{ background: '#F9731620', border: '1px solid #F9731660' }}>
            PIPELINE IN PAUSA
          </span>
        </div>

        {/* Modal body */}
        <div className="flex-1 overflow-hidden">
          {hitlType === 'outline_approval' && <OutlineDragList docId={activeDocId} />}
          {hitlType === 'section_approval' && <SectionReviewSplit docId={activeDocId} />}
          {hitlType === 'escalation' && <EscalationBanner docId={activeDocId} />}
          {!hitlType && (
            <div className="p-[24px] text-[13px] text-drs-muted font-mono">
              Attendere i dati dalla pipeline…
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
