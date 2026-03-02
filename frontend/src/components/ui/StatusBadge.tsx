// StatusBadge — renders a coloured dot + label for a NodeState status.
// Used in DocumentSidebar (SectionItem), AgentNode, and RightPanel.

type Status = 'waiting' | 'running' | 'completed' | 'failed' | 'skipped'

interface StatusBadgeProps {
  status: Status
  /** 'dot' shows only the coloured circle (e.g. collapsed sidebar) */
  variant?: 'full' | 'dot'
  size?: 'sm' | 'md'
}

const STATUS_CONFIG: Record<
  Status,
  { label: string; dotCls: string; textCls: string; pulse: boolean }
> = {
  waiting:   { label: 'In attesa',  dotCls: 'bg-drs-faint',  textCls: 'text-drs-faint',  pulse: false },
  running:   { label: 'In corso',   dotCls: 'bg-drs-green',  textCls: 'text-drs-green',  pulse: true  },
  completed: { label: 'Completato', dotCls: 'bg-drs-green',  textCls: 'text-drs-green',  pulse: false },
  failed:    { label: 'Fallito',    dotCls: 'bg-drs-red',    textCls: 'text-drs-red',    pulse: false },
  skipped:   { label: 'Saltato',    dotCls: 'bg-drs-muted',  textCls: 'text-drs-muted',  pulse: false },
}

export function StatusBadge({ status, variant = 'full', size = 'md' }: StatusBadgeProps) {
  const { label, dotCls, textCls, pulse } = STATUS_CONFIG[status]
  const dotSize  = size === 'sm' ? 'w-1.5 h-1.5' : 'w-2 h-2'
  const textSize = size === 'sm' ? 'text-xs'      : 'text-sm'

  return (
    <span className={`inline-flex items-center gap-1.5 ${textCls} ${textSize}`}>
      <span
        className={`rounded-full flex-shrink-0 ${dotSize} ${dotCls} ${
          pulse ? 'animate-dot-pulse' : ''
        }`}
      />
      {variant === 'full' && label}
    </span>
  )
}
