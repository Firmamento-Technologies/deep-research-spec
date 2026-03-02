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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 10, fontFamily: 'monospace', color: '#50536A', letterSpacing: 1 }}>
        JURY VERDICTS
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {ROWS.map((row, ri) => (
          <div key={ri} style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            <span
              style={{
                fontSize: 9,
                fontFamily: 'monospace',
                color: '#50536A',
                width: 10,
              }}
            >
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
                  style={{
                    flex: 1,
                    padding: '4px 2px',
                    background: bg,
                    border: `1px solid ${border}`,
                    borderRadius: 4,
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 1,
                  }}
                >
                  <span style={{ fontSize: 9, fontFamily: 'monospace', color: textColor, fontWeight: 700 }}>
                    {judgeId.toUpperCase()}
                  </span>
                  <span style={{ fontSize: 8, color: textColor }}>
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
        <div
          style={{
            background: '#0A0B0F',
            border: '1px solid #2A2D3A',
            borderRadius: 6,
            padding: '8px 10px',
            fontSize: 11,
            fontFamily: 'monospace',
            color: '#F0F1F6',
            lineHeight: 1.6,
          }}
        >
          {expandedVerdict.vetoCategory && (
            <div style={{ color: '#EF4444', marginBottom: 4, fontSize: 10 }}>
              VETO: {expandedVerdict.vetoCategory}
            </div>
          )}
          {expandedVerdict.confidence && (
            <div style={{ color: '#8B8FA8', marginBottom: 4, fontSize: 10 }}>
              Confidence: {expandedVerdict.confidence}
            </div>
          )}
          <div style={{ color: '#8B8FA8', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {expandedVerdict.reasoning ?? 'Nessun dettaglio disponibile.'}
          </div>
        </div>
      )}
    </div>
  )
}
