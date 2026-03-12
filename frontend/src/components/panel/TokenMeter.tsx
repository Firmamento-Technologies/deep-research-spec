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
    <div className="bg-drs-s1 border border-drs-border rounded-[6px] px-[12px] py-[8px] text-[11px] font-mono">
      <div className="text-drs-faint tracking-[1px] mb-[6px] text-[10px]">
        TOKEN &amp; COSTO
      </div>
      <div className="flex flex-col gap-[3px]">
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
    <div className="flex justify-between gap-[8px]">
      <span className="text-drs-faint">{label}:</span>
      <span style={{ color }}>{value}</span>
    </div>
  )
}
