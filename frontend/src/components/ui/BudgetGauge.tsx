// BudgetGauge — shows USD spent vs max budget with a coloured progress bar.
// Transitions: green → orange (50%) → yellow (70%) → red (90%).
// Used in RightPanel run overview and PipelineHeader.

import { ProgressBar } from './ProgressBar'

interface BudgetGaugeProps {
  spent: number
  max: number
  remainingPct: number
  className?: string
}

function fillColor(usedPct: number): string {
  if (usedPct >= 90) return 'bg-drs-red'
  if (usedPct >= 70) return 'bg-drs-yellow'
  if (usedPct >= 50) return 'bg-drs-orange'
  return 'bg-drs-green'
}

export function BudgetGauge({ spent, max, remainingPct, className = '' }: BudgetGaugeProps) {
  const usedPct = Math.min(100, 100 - remainingPct)

  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <div className="flex justify-between items-baseline">
        <span className="text-xs text-drs-muted">Budget</span>
        <span className="text-xs font-mono tabular-nums">
          <span className="text-drs-text">${spent.toFixed(2)}</span>
          <span className="text-drs-faint"> / ${max.toFixed(2)}</span>
        </span>
      </div>
      <ProgressBar
        value={usedPct}
        colorCls={fillColor(usedPct)}
        showLabel
      />
    </div>
  )
}
