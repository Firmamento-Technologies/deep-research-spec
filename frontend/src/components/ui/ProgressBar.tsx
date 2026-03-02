// ProgressBar — thin horizontal progress bar.
// Used in PipelineHeader (budget %), BudgetGauge, CSSGauge.

interface ProgressBarProps {
  /** 0–100 */
  value: number
  /** Tailwind bg-* class for the fill. Default: accent blue. */
  colorCls?: string
  showLabel?: boolean
  className?: string
}

export function ProgressBar({
  value,
  colorCls = 'bg-drs-accent',
  showLabel = false,
  className = '',
}: ProgressBarProps) {
  const pct = Math.min(100, Math.max(0, value))

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="flex-1 h-1.5 rounded-full bg-drs-border overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${colorCls}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-xs text-drs-muted font-mono tabular-nums w-8 text-right">
          {Math.round(pct)}%
        </span>
      )}
    </div>
  )
}
