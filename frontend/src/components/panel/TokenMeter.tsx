// TokenMeter — live token usage display

interface TokenMeterProps {
  tokensIn?: number
  tokensOut?: number
  tokensOutEst?: number
  costUsd?: number
  isLive?: boolean
}

function formatK(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`
}

export function TokenMeter({ tokensIn, tokensOut, tokensOutEst, costUsd, isLive }: TokenMeterProps) {
  return (
    <div
      style={{
        background: '#111318',
        border: '1px solid #2A2D3A',
        borderRadius: 6,
        padding: '8px 12px',
        fontSize: 11,
        fontFamily: 'monospace',
      }}
    >
      <div style={{ color: '#50536A', letterSpacing: 1, marginBottom: 6, fontSize: 10 }}>
        TOKEN &amp; COSTO
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Row
          label="Input"
          value={tokensIn != null ? `${formatK(tokensIn)} token` : '—'}
          color="#8B8FA8"
        />
        <Row
          label="Output"
          value={
            tokensOut != null
              ? `${formatK(tokensOut)}${tokensOutEst != null && isLive ? ` / ~${formatK(tokensOutEst)} est.` : ''}`
              : '—'
          }
          color={isLive ? '#22C55E' : '#8B8FA8'}
        />
        <Row
          label="Costo"
          value={costUsd != null ? `$${costUsd.toFixed(4)}` : '—'}
          color="#EAB308"
        />
      </div>
    </div>
  )
}

function Row({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
      <span style={{ color: '#50536A' }}>{label}:</span>
      <span style={{ color }}>{value}</span>
    </div>
  )
}
