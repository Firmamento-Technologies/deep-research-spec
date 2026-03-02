import React, { useState } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'

interface EscalationBannerProps {
  docId: string
}

export function EscalationBanner({ docId }: EscalationBannerProps) {
  const { setState } = useAppStore()
  const { activeRun } = useRunStore()

  const payload = (activeRun as any)?.hitlPayload ?? {}
  const escalationType: string = payload.escalationType  ?? 'ESCALATION'
  const description: string    = payload.description     ?? 'Azione richiesta per risolvere un conflitto nella pipeline.'

  const [submitting, setSubmitting] = useState(false)
  const [error, setError]           = useState<string | null>(null)

  const resolve = async (action: 'auto' | 'manual' | 'skip', resolution?: string) => {
    setSubmitting(true)
    setError(null)
    try {
      const res = await fetch(`/api/runs/${docId}/resolve-escalation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, ...(resolution ? { resolution } : {}) }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setState('PROCESSING')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      style={{
        padding: 24,
        display: 'flex',
        flexDirection: 'column',
        gap: 20,
      }}
    >
      {/* Red banner */}
      <div
        style={{
          background: '#EF444415',
          border: '1px solid #EF4444',
          borderRadius: 8,
          padding: '14px 18px',
        }}
      >
        <div
          style={{
            fontSize: 13,
            fontFamily: 'monospace',
            color: '#EF4444',
            fontWeight: 700,
            marginBottom: 8,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <span
            style={{
              width: 10, height: 10, borderRadius: '50%',
              background: '#EF4444',
              boxShadow: '0 0 8px #EF4444',
              display: 'inline-block',
              flexShrink: 0,
            }}
          />
          {escalationType}
        </div>
        <div style={{ fontSize: 13, color: '#F0F1F6', lineHeight: 1.7 }}>
          {description}
        </div>
      </div>

      {/* Context detail */}
      {payload.detail && (
        <div
          style={{
            background: '#111318',
            border: '1px solid #2A2D3A',
            borderRadius: 6,
            padding: '12px 14px',
            fontSize: 12,
            fontFamily: 'monospace',
            color: '#8B8FA8',
            lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {payload.detail}
        </div>
      )}

      {error && (
        <div style={{ fontSize: 11, color: '#EF4444', fontFamily: 'monospace' }}>{error}</div>
      )}

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
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
      style={{
        flex: 1,
        minWidth: 160,
        padding: '14px 16px',
        background: `${color}10`,
        border: `1px solid ${color}60`,
        borderRadius: 8,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        textAlign: 'left',
        transition: 'background 0.15s, border-color 0.15s',
      }}
      onMouseEnter={e => { if (!disabled) (e.currentTarget as HTMLButtonElement).style.background = `${color}20` }}
      onMouseLeave={e => { if (!disabled) (e.currentTarget as HTMLButtonElement).style.background = `${color}10` }}
    >
      <div style={{ fontSize: 12, fontFamily: 'monospace', color, fontWeight: 700, marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ fontSize: 11, color: '#8B8FA8', lineHeight: 1.4 }}>
        {description}
      </div>
    </button>
  )
}
