// StatusBadge — visual indicator for a node/section status.
// Used in SectionItem (variant='dot') and AgentNode detail panel (STEP 8).

import type { NodeStatus } from '../../types/run'

interface StatusBadgeProps {
  status: NodeStatus
  variant?: 'dot' | 'icon' | 'text'
  size?:    'sm' | 'md'
}

const DOT_CLASS: Record<NodeStatus, string> = {
  waiting:   'bg-drs-s3',
  running:   'bg-drs-accent animate-dot-pulse',
  completed: 'bg-drs-green',
  failed:    'bg-drs-red',
  skipped:   'bg-drs-muted opacity-40',
}

const STATUS_ICON: Record<NodeStatus, string> = {
  waiting:   '⏳',
  running:   '▶',
  completed: '✓',
  failed:    '✕',
  skipped:   '↦',
}

const STATUS_TEXT: Record<NodeStatus, string> = {
  waiting:   'In attesa',
  running:   'In corso',
  completed: 'Completato',
  failed:    'Fallito',
  skipped:   'Saltato',
}

const STATUS_TEXT_COLOR: Record<NodeStatus, string> = {
  waiting:   'text-drs-faint',
  running:   'text-drs-accent',
  completed: 'text-drs-green',
  failed:    'text-drs-red',
  skipped:   'text-drs-muted',
}

export function StatusBadge({ status, variant = 'dot', size = 'md' }: StatusBadgeProps) {
  if (variant === 'icon') {
    return (
      <span className={`text-sm ${STATUS_TEXT_COLOR[status]}`}>
        {STATUS_ICON[status]}
      </span>
    )
  }

  if (variant === 'text') {
    return (
      <span className={`text-xs font-mono ${STATUS_TEXT_COLOR[status]}`}>
        {STATUS_TEXT[status]}
      </span>
    )
  }

  // dot (default)
  const sizeClass = size === 'sm' ? 'w-1.5 h-1.5' : 'w-2 h-2'
  return (
    <span
      className={`inline-block rounded-full shrink-0 ${sizeClass} ${DOT_CLASS[status]}`}
    />
  )
}
