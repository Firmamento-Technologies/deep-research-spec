import React, { useEffect, useRef } from 'react'

interface AgentLogPanelProps {
  text: string
  isLive: boolean
}

export function AgentLogPanel({ text, isLive }: AgentLogPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isLive && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [text, isLive])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div
        style={{
          fontSize: 10,
          fontFamily: 'monospace',
          color: '#50536A',
          letterSpacing: 1,
        }}
      >
        {isLive ? 'OUTPUT LIVE' : 'OUTPUT'}
      </div>
      <div
        style={{
          background: '#0A0B0F',
          border: '1px solid #2A2D3A',
          borderRadius: 6,
          padding: '8px 10px',
          maxHeight: isLive ? 240 : 140,
          overflowY: 'auto',
          fontSize: 11,
          fontFamily: 'monospace',
          color: '#F0F1F6',
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {text || <span style={{ color: '#50536A' }}>In attesa di output…</span>}
        {isLive && (
          <span
            style={{
              display: 'inline-block',
              width: 7,
              height: 13,
              background: '#7C8CFF',
              marginLeft: 2,
              animation: 'blink 1s step-start infinite',
            }}
          />
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
