// ModelBadge — compact clickable badge showing the active model name.
// Used in Topbar (center, companion model) and in AgentNode (running/selected state).
// Clicking triggers the model change dropdown (handled by parent).

interface ModelBadgeProps {
  model: string
  onClick?: () => void
  /** If true, renders as a non-interactive span (e.g. inside AgentNode label) */
  readOnly?: boolean
}

/** Maps full OpenRouter model IDs to short display names. */
function shortName(model: string): string {
  const map: Record<string, string> = {
    'anthropic/claude-opus-4-6':    'Claude Opus 4.6',
    'anthropic/claude-sonnet-4-6':  'Claude Sonnet 4.6',
    'anthropic/claude-haiku-3':     'Claude Haiku 3',
    'openai/o3':                    'OpenAI o3',
    'openai/o3-mini':               'OpenAI o3 mini',
    'google/gemini-3.1-pro':        'Gemini 3.1 Pro',
    'perplexity/sonar-pro':         'Sonar Pro',
    'qwen/qwen3-7b':                'Qwen3 7B',
  }
  return map[model] ?? model.split('/').pop() ?? model
}

export function ModelBadge({ model, onClick, readOnly = false }: ModelBadgeProps) {
  const label = shortName(model)

  const baseClass =
    'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded ' +
    'bg-drs-s2 border border-drs-border text-drs-muted text-xs font-mono ' +
    'transition-colors'

  if (readOnly) {
    return (
      <span className={baseClass}>
        <span className="w-1.5 h-1.5 rounded-full bg-drs-accent flex-shrink-0" />
        {label}
      </span>
    )
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={`${baseClass} hover:border-drs-border-bright hover:text-drs-text cursor-pointer`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-drs-accent flex-shrink-0" />
      {label}
      <span className="text-drs-faint ml-0.5">▾</span>
    </button>
  )
}
