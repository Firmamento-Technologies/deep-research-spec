import { useState } from 'react'

export interface JudgeVerdict {
  judgeId: string   // r1,r2,r3,f1,f2,f3,s1,s2,s3
  pass: boolean
  reasoning?: string
  vetoCategory?: string
  confidence?: 'low' | 'medium' | 'high'
}

interface JuryVerdictGridProps {
  verdicts: JudgeVerdict[]
}

const ROWS = [
  ['r1', 'r2', 'r3'],
  ['f1', 'f2', 'f3'],
  ['s1', 's2', 's3'],
]

const ROW_LABELS = ['R', 'F', 'S']

export function JuryVerdictGrid({ verdicts }: JuryVerdictGridProps) {
  const [expanded, setExpanded] = useState<string | null>(null)

  const map = Object.fromEntries(verdicts.map(v => [v.judgeId, v]))

  const expandedVerdict = expanded ? map[expanded] : null

  return (
    <div className="flex flex-col gap-[8px]">
      <div className="text-[10px] font-mono text-drs-faint tracking-[1px]">
        JURY VERDICTS
      </div>

      <div className="flex flex-col gap-[4px]">
        {ROWS.map((row, ri) => (
          <div key={ri} className="flex gap-[4px] items-center">
            <span className="text-[9px] font-mono text-drs-faint w-[10px]">
              {ROW_LABELS[ri]}
            </span>
            {row.map(judgeId => {
              const v = map[judgeId]
              const isVeto = !!v?.vetoCategory
              const isPass = v?.pass ?? null
              const isSelected = expanded === judgeId

              let bg = '#1A1D27'
              let border = '#2A2D3A'
              let textColor = '#50536A'

              if (isVeto) {
                bg = '#EF444420'
                border = '#EF4444'
                textColor = '#EF4444'
              } else if (isPass === true) {
                bg = '#22C55E15'
                border = '#22C55E80'
                textColor = '#22C55E'
              } else if (isPass === false) {
                bg = '#EF444415'
                border = '#EF444480'
                textColor = '#EF4444'
              }

              if (isSelected) border = '#F0F1F6'

              return (
                <button
                  key={judgeId}
                  onClick={() => setExpanded(expanded === judgeId ? null : judgeId)}
                  aria-label={`Giudice ${judgeId.toUpperCase()}: ${v == null ? 'in attesa' : isVeto ? 'VETO' : isPass ? 'approvato' : 'rifiutato'}`}
                  aria-expanded={isSelected}
                  className="flex-1 flex flex-col items-center gap-[1px] rounded-input cursor-pointer"
                  style={{
                    padding: '4px 2px',
                    background: bg,
                    border: `1px solid ${border}`,
                  }}
                >
                  <span className="text-[9px] font-mono font-bold" style={{ color: textColor }}>
                    {judgeId.toUpperCase()}
                  </span>
                  <span className="text-[8px]" style={{ color: textColor }}>
                    {v == null ? '—' : isVeto ? '🔴 VETO' : isPass ? '✓' : '×'}
                  </span>
                </button>
              )
            })}
          </div>
        ))}
      </div>

      {/* Expanded reasoning */}
      {expandedVerdict && (
        <div className="bg-drs-bg border border-drs-border rounded-[6px] px-[10px] py-[8px] text-[11px] font-mono text-drs-text leading-[1.6]">
          {expandedVerdict.vetoCategory && (
            <div className="text-drs-red mb-[4px] text-[10px]">
              VETO: {expandedVerdict.vetoCategory}
            </div>
          )}
          {expandedVerdict.confidence && (
            <div className="text-drs-muted mb-[4px] text-[10px]">
              Confidence: {expandedVerdict.confidence}
            </div>
          )}
          <div className="text-drs-muted whitespace-pre-wrap break-words">
            {expandedVerdict.reasoning ?? 'Nessun dettaglio disponibile.'}
          </div>
        </div>
      )}
    </div>
  )
}
