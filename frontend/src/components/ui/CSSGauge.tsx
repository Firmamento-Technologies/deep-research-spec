// CSSGauge — three-row gauge for Consensus Strength Score.
// Thresholds: Content ≥0.65, Style ≥0.80, Source ≥0.60 (from jury system spec).
// Used in RightPanel run overview and in the right panel when no node is selected.

import { ProgressBar } from './ProgressBar'

export interface CSSScores {
  content: number
  style: number
  source: number
}

interface CSSGaugeProps {
  scores: CSSScores
  className?: string
}

const ROWS = [
  { key: 'content' as const, label: 'Content', threshold: 0.65 },
  { key: 'style'   as const, label: 'Style',   threshold: 0.80 },
  { key: 'source'  as const, label: 'Source',  threshold: 0.60 },
]

function colorCls(value: number, threshold: number): string {
  if (value >= threshold)          return 'bg-drs-green'
  if (value >= threshold * 0.875)  return 'bg-drs-yellow'
  return 'bg-drs-red'
}

export function CSSGauge({ scores, className = '' }: CSSGaugeProps) {
  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {ROWS.map(({ key, label, threshold }) => {
        const value = scores[key]
        return (
          <div key={key} className="flex items-center gap-2">
            <span className="text-xs text-drs-muted w-14 flex-shrink-0">{label}</span>
            <ProgressBar
              value={value * 100}
              colorCls={colorCls(value, threshold)}
              className="flex-1"
            />
            <span
              className={`text-xs font-mono tabular-nums w-10 text-right ${
                value >= threshold ? 'text-drs-green' : 'text-drs-red'
              }`}
            >
              {value.toFixed(2)}
            </span>
            <span className="text-xs text-drs-faint w-8 flex-shrink-0">
              &ge;{threshold.toFixed(2)}
            </span>
          </div>
        )
      })}
    </div>
  )
}
