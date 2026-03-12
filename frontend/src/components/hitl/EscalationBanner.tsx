import { useState } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'
import { api } from '../../lib/api'

interface EscalationBannerProps {
  docId: string
}

export function EscalationBanner({ docId }: EscalationBannerProps) {
  const { setState } = useAppStore()
  const { activeRun } = useRunStore()

  const payload = (activeRun as any)?.hitlPayload ?? {}
  const escalationType: string = payload.escalationType ?? 'ESCALATION'
  const description: string = payload.description ?? 'Azione richiesta per risolvere un conflitto nella pipeline.'

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const resolve = async (action: 'auto' | 'manual' | 'skip', resolution?: string) => {
    setSubmitting(true)
    setError(null)
    try {
      await api.post(`/api/runs/${docId}/resolve-escalation`, {
        action,
        ...(resolution ? { resolution } : {}),
      })
      setState('PROCESSING')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="p-[24px] flex flex-col gap-[20px]">
      {/* Red banner */}
      <div className="rounded-card p-[14px_18px]" style={{ background: '#EF444415', border: '1px solid #EF4444' }}>
        <div className="text-[13px] font-mono text-drs-red font-bold mb-[8px] flex items-center gap-[8px]">
          <span className="w-[10px] h-[10px] rounded-full bg-drs-red inline-block shrink-0 shadow-[0_0_8px_#EF4444]" />
          {escalationType}
        </div>
        <div className="text-[13px] text-drs-text leading-[1.7]">
          {description}
        </div>
      </div>

      {/* Context detail */}
      {payload.detail && (
        <div className="bg-drs-s1 border border-drs-border rounded-[6px] p-[12px_14px] text-[12px] font-mono text-drs-muted leading-[1.6] whitespace-pre-wrap break-words">
          {payload.detail}
        </div>
      )}

      {error && (
        <div className="text-[11px] text-drs-red font-mono">{error}</div>
      )}

      {/* Action buttons */}
      <div className="flex gap-[12px] flex-wrap">
        <EscalationBtn
          label="Risolvi Automatico"
          description="Lascia che la pipeline risolva il conflitto automaticamente."
          color="#22C55E"
          disabled={submitting}
          onClick={() => resolve('auto')}
        />
        <EscalationBtn
          label="Modifica Manuale"
          description="Intervieni manualmente per correggere il conflitto."
          color="#7C8CFF"
          disabled={submitting}
          onClick={() => resolve('manual')}
        />
        <EscalationBtn
          label="Salta Sezione"
          description="Ignora questa sezione e procedi con la prossima."
          color="#F97316"
          disabled={submitting}
          onClick={() => resolve('skip')}
        />
      </div>
    </div>
  )
}

function EscalationBtn({
  label, description, color, disabled, onClick,
}: {
  label: string
  description: string
  color: string
  disabled: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex-1 min-w-[160px] p-[14px_16px] rounded-card text-left transition-[background,border-color] duration-150 ${
        disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer opacity-100'
      }`}
      style={{
        background: `${color}10`,
        border: `1px solid ${color}60`,
      }}
      onMouseEnter={e => { if (!disabled) (e.currentTarget as HTMLButtonElement).style.background = `${color}20` }}
      onMouseLeave={e => { if (!disabled) (e.currentTarget as HTMLButtonElement).style.background = `${color}10` }}
    >
      <div className="text-[12px] font-mono font-bold mb-[4px]" style={{ color }}>
        {label}
      </div>
      <div className="text-[11px] text-drs-muted leading-[1.4]">
        {description}
      </div>
    </button>
  )
}
