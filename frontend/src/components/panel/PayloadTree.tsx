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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ fontSize: 10, fontFamily: 'monospace', color: '#50536A', letterSpacing: 1 }}>
        PAYLOAD INPUT
      </div>
      {sections.map((sec, i) => {
        const isOpen = expanded.has(i)
        return (
          <div key={i}>
            <button
              onClick={() => toggle(i)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                width: '100%',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                padding: '3px 0',
                textAlign: 'left',
              }}
            >
              <span style={{ fontSize: 10, color: '#50536A' }}>{isOpen ? '▾' : '▸'}</span>
              <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#8B8FA8' }}>
                {sec.label}
              </span>
              <span style={{ fontSize: 10, color: '#50536A' }}>
                ({formatK(sec.tokens)} tok)
              </span>
              <span style={{ fontSize: 10, color: '#7C8CFF', marginLeft: 'auto' }}>
                [espandi]
              </span>
            </button>
            {isOpen && (
              <div
                style={{
                  background: '#0A0B0F',
                  border: '1px solid #2A2D3A',
                  borderRadius: 4,
                  padding: '6px 8px',
                  fontSize: 10,
                  fontFamily: 'monospace',
                  color: '#8B8FA8',
                  maxHeight: 160,
                  overflowY: 'auto',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  lineHeight: 1.5,
                }}
              >
                {sec.content}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
