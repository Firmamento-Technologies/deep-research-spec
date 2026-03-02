// ModelBadge — pill showing an OpenRouter model name.
// Used in Topbar (companion model) and AgentNode right-panel (STEP 8).
// Clickable when onClick is provided.

interface ModelBadgeProps {
  model: string         // e.g. 'anthropic/claude-sonnet-4-6'
  onClick?: () => void
}

/** 'anthropic/claude-sonnet-4-6' → 'Claude Sonnet 4.6' */
function toDisplayName(model: string): string {
  const after = model.split('/').pop() ?? model
  return after
    .replace(/-/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export function ModelBadge({ model, onClick }: ModelBadgeProps) {
  return (
    <button
      onClick={onClick}
      disabled={!onClick}
      className={
        'px-2.5 py-1 rounded ' +
        'bg-drs-s2 border border-drs-border ' +
        'text-xs font-mono text-drs-muted ' +
        (onClick
          ? 'hover:border-drs-border-bright hover:text-drs-text cursor-pointer'
          : 'cursor-default') +
        ' transition-colors'
      }
      title={model}
    >
      {toDisplayName(model)}
    </button>
  )
}
