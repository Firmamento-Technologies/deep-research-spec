import { useState } from 'react'

export interface Source {
  url: string
  title: string
  snippet: string
  reliabilityScore: number
}

interface SourceListProps {
  sources: Source[]
}

function ReliabilityBadge({ score }: { score: number }) {
  const color =
    score >= 0.85 ? '#22C55E' :
      score >= 0.70 ? '#EAB308' :
        '#EF4444'
  return (
    <span
      style={{
        display: 'inline-block',
        background: `${color}20`,
        border: `1px solid ${color}80`,
        borderRadius: 4,
        padding: '1px 5px',
        fontSize: 10,
        fontFamily: 'monospace',
        color,
        minWidth: 36,
        textAlign: 'center',
      }}
    >
      {score.toFixed(2)}
    </span>
  )
}

export function SourceList({ sources }: SourceListProps) {
  const [expanded, setExpanded] = useState<number | null>(null)

  if (!sources.length) {
    return (
      <div style={{ fontSize: 11, fontFamily: 'monospace', color: '#50536A' }}>
        Nessuna fonte disponibile.
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ fontSize: 10, fontFamily: 'monospace', color: '#50536A', letterSpacing: 1 }}>
        FONTI
      </div>
      {sources.map((src, i) => {
        const domain = (() => {
          try { return new URL(src.url).hostname }
          catch { return src.url }
        })()
        const isOpen = expanded === i
        return (
          <div
            key={i}
            style={{
              background: '#111318',
              border: '1px solid #2A2D3A',
              borderRadius: 6,
              padding: '7px 10px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
              <ReliabilityBadge score={src.reliabilityScore} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 11,
                    fontFamily: 'monospace',
                    color: '#7C8CFF',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {domain}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: '#F0F1F6',
                    marginTop: 2,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: isOpen ? 'normal' : 'nowrap',
                    cursor: 'pointer',
                  }}
                  onClick={() => setExpanded(isOpen ? null : i)}
                >
                  {src.title}
                </div>
                {isOpen && (
                  <div
                    style={{
                      fontSize: 10,
                      color: '#8B8FA8',
                      marginTop: 4,
                      lineHeight: 1.5,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {src.snippet}
                  </div>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
