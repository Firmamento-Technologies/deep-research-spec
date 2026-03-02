import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'
import { OutlineDragList } from './OutlineDragList'
import { SectionReviewSplit } from './SectionReviewSplit'
import { EscalationBanner } from './EscalationBanner'

/**
 * HumanRequiredModal
 * Triggered when appState === 'AWAITING_HUMAN'.
 * Full-screen overlay — NOT dismissible by clicking outside or pressing Escape.
 * Type is read from activeRun.hitlType (set by useSSE when HUMAN_REQUIRED fires).
 */
export function HumanRequiredModal() {
  const { state: appState, activeDocId } = useAppStore()
  const { activeRun } = useRunStore()

  if (appState !== 'AWAITING_HUMAN' || !activeDocId) return null

  const hitlType = (activeRun as any)?.hitlType as
    | 'outline_approval'
    | 'section_approval'
    | 'escalation'
    | undefined

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        background: 'rgba(0,0,0,0.85)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backdropFilter: 'blur(4px)',
      }}
    // NOT dismissible — no onClick on overlay
    >
      <div
        style={{
          background: '#111318',
          border: '1px solid #2A2D3A',
          borderRadius: 12,
          width: '90vw',
          maxWidth: hitlType === 'section_approval' ? 1100 : 680,
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          boxShadow: '0 24px 64px rgba(0,0,0,0.7)',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Modal header */}
        <div
          style={{
            padding: '14px 20px',
            borderBottom: '1px solid #2A2D3A',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            flexShrink: 0,
          }}
        >
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: '#F97316',
              boxShadow: '0 0 8px #F97316',
              display: 'inline-block',
            }}
          />
          <span style={{ fontSize: 13, fontFamily: 'monospace', color: '#F0F1F6', fontWeight: 700 }}>
            {hitlType === 'outline_approval' && 'APPROVAZIONE OUTLINE'}
            {hitlType === 'section_approval' && 'REVISIONE SEZIONE'}
            {hitlType === 'escalation' && 'ESCALATION — AZIONE RICHIESTA'}
            {!hitlType && 'AZIONE RICHIESTA'}
          </span>
          <span
            style={{
              marginLeft: 'auto',
              fontSize: 10,
              fontFamily: 'monospace',
              color: '#F97316',
              background: '#F9731620',
              border: '1px solid #F9731660',
              borderRadius: 3,
              padding: '2px 8px',
            }}
          >
            PIPELINE IN PAUSA
          </span>
        </div>

        {/* Modal body */}
        <div style={{ flex: 1, overflow: 'hidden' }}>
          {hitlType === 'outline_approval' && <OutlineDragList docId={activeDocId} />}
          {hitlType === 'section_approval' && <SectionReviewSplit docId={activeDocId} />}
          {hitlType === 'escalation' && <EscalationBanner docId={activeDocId} />}
          {!hitlType && (
            <div style={{ padding: 24, fontSize: 13, color: '#8B8FA8', fontFamily: 'monospace' }}>
              Attendere i dati dalla pipeline…
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
