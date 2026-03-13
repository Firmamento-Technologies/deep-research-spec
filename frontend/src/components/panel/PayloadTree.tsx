import { useState } from 'react'

interface PayloadSection {
  label: string
  tokens: number
  content: string
}

interface PayloadTreeProps {
  sections: PayloadSection[]
}

function formatK(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`
}

export function PayloadTree({ sections }: PayloadTreeProps) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  const toggle = (i: number) =>
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })

  if (!sections.length) return null

  return (
    <div className="flex flex-col gap-[4px]">
      <div className="text-[10px] font-mono text-drs-faint tracking-[1px]">
        PAYLOAD INPUT
      </div>
      {sections.map((sec, i) => {
        const isOpen = expanded.has(i)
        return (
          <div key={i}>
            <button
              onClick={() => toggle(i)}
              className="flex items-center gap-[6px] w-full bg-transparent border-none cursor-pointer py-[3px] px-0 text-left transition-colors hover:bg-drs-s2/30 rounded"
              aria-label={`${isOpen ? 'Comprimi' : 'Espandi'} ${sec.label}`}
            >
              <span className="text-[10px] text-drs-faint">{isOpen ? '▾' : '▸'}</span>
              <span className="text-[11px] font-mono text-drs-muted">
                {sec.label}
              </span>
              <span className="text-[10px] text-drs-faint">
                ({formatK(sec.tokens)} tok)
              </span>
              <span className="text-[10px] text-drs-accent ml-auto">
                [espandi]
              </span>
            </button>
            {isOpen && (
              <div className="bg-drs-bg border border-drs-border rounded-input p-[6px_8px] text-[10px] font-mono text-drs-muted max-h-[160px] overflow-y-auto whitespace-pre-wrap break-words leading-[1.5]">
                {sec.content}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
