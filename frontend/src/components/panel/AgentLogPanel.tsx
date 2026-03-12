import { useEffect, useRef } from 'react'

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
    <div className="flex flex-col gap-[6px]">
      <div className="text-[10px] font-mono text-drs-faint tracking-[1px]">
        {isLive ? 'OUTPUT LIVE' : 'OUTPUT'}
      </div>
      <div
        className="bg-drs-bg border border-drs-border rounded-[6px] px-[10px] py-[8px] text-[11px] font-mono text-drs-text leading-[1.6] whitespace-pre-wrap break-words overflow-y-auto"
        style={{ maxHeight: isLive ? 240 : 140 }}
      >
        {text || <span className="text-drs-faint">In attesa di output…</span>}
        {isLive && (
          <span
            className="inline-block w-[7px] h-[13px] bg-drs-accent ml-[2px]"
            style={{ animation: 'blink 1s step-start infinite' }}
          />
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
