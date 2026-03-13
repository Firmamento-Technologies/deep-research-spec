import type { ReactNode } from 'react'
import type { RunState } from '../../store/useRunStore'
import { useAppStore } from '../../store/useAppStore'

interface PipelineHeaderProps {
  run: RunState | null
}

export function PipelineHeader({ run }: PipelineHeaderProps) {
  const setState = useAppStore((s) => s.setState)

  if (!run) return null

  const budgetPct = run.maxBudget > 0
    ? Math.round((run.budgetSpent / run.maxBudget) * 100)
    : 0
  const budgetColor =
    budgetPct >= 90 ? '#EF4444' :
    budgetPct >= 70 ? '#EAB308' :
    '#22C55E'

  return (
    <div className="absolute top-0 left-0 right-0 z-30 bg-drs-s1/95 backdrop-blur-sm border-b border-drs-border px-4 py-2 flex items-center gap-3 text-[12px] font-mono shadow-md">
      {/* Topic */}
      <span className="text-drs-accent font-semibold truncate max-w-[200px]">
        {run.topic}
      </span>

      <Divider />

      {/* Section counter */}
      <Chip>
        <span className="text-drs-faint">Sez.</span>
        <span className="text-drs-accent">{run.currentSection}</span>
        <span className="text-drs-faint">/{run.totalSections}</span>
      </Chip>

      {/* Budget */}
      <Chip>
        <span style={{ color: budgetColor }}>${run.budgetSpent.toFixed(2)}</span>
        <span className="text-drs-faint">/ ${run.maxBudget.toFixed(0)}</span>
        <div className="w-16 h-1.5 bg-drs-s2 rounded-full overflow-hidden ml-1">
          <div
            className="h-full rounded-full transition-[width] duration-300"
            style={{ width: `${Math.min(100, budgetPct)}%`, background: budgetColor }}
          />
        </div>
        <span className="text-[10px]" style={{ color: budgetColor }}>{budgetPct}%</span>
      </Chip>

      {/* CSS Scores */}
      {run.cssScores && (
        <Chip>
          <span className="text-drs-faint">CSS</span>
          <Score label="C" value={run.cssScores.content} threshold={0.65} />
          <Score label="S" value={run.cssScores.style} threshold={0.80} />
          <Score label="R" value={run.cssScores.source} threshold={0.70} />
        </Chip>
      )}

      <span className="ml-auto" />

      {/* Companion button */}
      <button
        onClick={() => setState('CONVERSING')}
        className="bg-drs-accent/15 text-drs-accent border border-drs-accent/30 rounded-md px-3 py-1 font-mono text-[11px] cursor-pointer hover:bg-drs-accent/25 transition-colors"
      >
        Companion
      </button>
    </div>
  )
}

function Divider() {
  return <div className="w-px h-4 bg-drs-border" />
}

function Chip({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-1.5 bg-drs-s2/60 rounded-md px-2 py-1 text-[11px]">
      {children}
    </div>
  )
}

function Score({ label, value, threshold }: { label: string; value: number; threshold: number }) {
  const color = value >= threshold ? '#22C55E' : value > 0 ? '#EF4444' : '#50536A'
  return (
    <span style={{ color }}>
      {label}:{value > 0 ? value.toFixed(2) : '—'}
    </span>
  )
}
