// SectionItem — a single section row in DocumentSidebar.
// Shows: status dot, section number + title, hover micro-menu.
// Spec: UI_BUILD_PLAN.md Section 5.

import { useState } from 'react'
import { StatusBadge } from '../ui/StatusBadge'
import { useAppStore } from '../../store/useAppStore'
import type { SectionResult, NodeStatus } from '../../types/run'

interface SectionItemProps {
  section: SectionResult
  isRunning?: boolean
}

function resolveStatus(section: SectionResult, isRunning?: boolean): NodeStatus {
  if (isRunning)      return 'running'
  if (section.approved) return 'completed'
  return 'waiting'
}

export function SectionItem({ section, isRunning }: SectionItemProps) {
  const [hovered, setHovered] = useState(false)
  const setState = useAppStore((s) => s.setState)
  const status   = resolveStatus(section, isRunning)

  const handleClick = () => {
    if (section.approved) setState('REVIEWING')
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onKeyDown={(e) => e.key === 'Enter' && handleClick()}
      className={
        'relative flex items-center gap-1.5 px-1 py-1 rounded text-xs ' +
        'hover:bg-drs-s2 cursor-pointer transition-colors group'
      }
    >
      {/* Status dot */}
      <StatusBadge status={status} variant="dot" size="sm" />

      {/* Label */}
      <span className="text-drs-muted group-hover:text-drs-text transition-colors truncate flex-1">
        § {section.idx + 1} {section.title}
      </span>

      {/* Micro-menu — visible on hover for completed sections */}
      {hovered && section.approved && (
        <div className="absolute right-1 flex items-center gap-0.5 bg-drs-s2 rounded px-0.5">
          {(
            [['\u2b07', 'DOCX'], ['\u29c9', 'Copia'], ['\u22ee', 'Log']] as const
          ).map(([icon, label]) => (
            <button
              key={label}
              onClick={(e) => e.stopPropagation()}
              title={label}
              className={
                'w-5 h-5 flex items-center justify-center rounded ' +
                'text-drs-faint hover:text-drs-text hover:bg-drs-s3 ' +
                'transition-colors text-[10px]'
              }
            >
              {icon}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
