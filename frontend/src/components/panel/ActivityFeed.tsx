import { useEffect, useRef } from 'react'
import { useRunStore } from '../../store/useRunStore'
import type { ActivityEntry } from '../../store/useRunStore'

export function ActivityFeed() {
  const feed = useRunStore((s) => s.activityFeed)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [feed.length])

  if (feed.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <div className="text-[24px] mb-[8px]" style={{ opacity: 0.3 }}>&#9678;</div>
          <div className="text-[11px] font-mono text-drs-faint">
            In attesa di eventi...
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-[2px]">
      {feed.map((entry) => (
        <FeedEntry key={entry.id} entry={entry} />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}

function FeedEntry({ entry }: { entry: ActivityEntry }) {
  const time = entry.ts.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  return (
    <div className="flex gap-[8px] py-[4px] px-[2px] rounded hover:bg-drs-s2/50 transition-colors">
      <span
        className="text-[12px] shrink-0 w-[16px] text-center leading-[20px]"
        style={{ color: entry.color ?? '#8B8FA8' }}
      >
        {entry.icon}
      </span>
      <div className="flex-1 min-w-0">
        <div className="text-[11px] font-mono text-drs-text leading-[20px] truncate">
          {entry.text}
        </div>
        {entry.detail && (
          <div className="text-[10px] font-mono text-drs-faint leading-[16px] truncate">
            {entry.detail}
          </div>
        )}
      </div>
      <span className="text-[9px] font-mono text-drs-faint shrink-0 leading-[20px]">
        {time}
      </span>
    </div>
  )
}
