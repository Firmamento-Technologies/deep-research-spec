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
      className="inline-block rounded-input text-[10px] font-mono min-w-[36px] text-center"
      style={{
        background: `${color}20`,
        border: `1px solid ${color}80`,
        padding: '1px 5px',
        color,
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
      <div className="text-[11px] font-mono text-drs-faint">
        Nessuna fonte disponibile.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-[6px]">
      <div className="text-[10px] font-mono text-drs-faint tracking-[1px]">
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
            className="bg-drs-s1 border border-drs-border rounded-[6px] p-[7px_10px]"
          >
            <div className="flex items-start gap-[6px]">
              <ReliabilityBadge score={src.reliabilityScore} />
              <div className="flex-1 min-w-0">
                <div className="text-[11px] font-mono text-drs-accent overflow-hidden text-ellipsis whitespace-nowrap">
                  {domain}
                </div>
                <div
                  className={`text-[11px] text-drs-text mt-[2px] overflow-hidden text-ellipsis cursor-pointer ${isOpen ? 'whitespace-normal' : 'whitespace-nowrap'}`}
                  onClick={() => setExpanded(isOpen ? null : i)}
                >
                  {src.title}
                </div>
                {isOpen && (
                  <div className="text-[10px] text-drs-muted mt-[4px] leading-[1.5] whitespace-pre-wrap break-words">
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
