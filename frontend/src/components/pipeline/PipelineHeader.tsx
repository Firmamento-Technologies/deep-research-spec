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
  const budgetBarWidth = Math.min(100, budgetPct)
  const budgetColor =
    budgetPct >= 90 ? '#EF4444' :
      budgetPct >= 70 ? '#EAB308' :
        '#22C55E'

  const filledBars = Math.round(budgetBarWidth / 10)
  const bar = '█'.repeat(filledBars) + '░'.repeat(10 - filledBars)

  return (
    <div
      className="absolute top-0 left-0 right-0 z-30 bg-[rgba(10,11,15,0.88)] border-b border-drs-border px-[12px] py-[6px] flex items-center gap-[12px] text-[12px] font-mono text-drs-text backdrop-blur-[4px] flex-wrap"
    >
      <span className="text-drs-accent font-semibold">
        {run.topic.length > 40 ? run.topic.slice(0, 40) + '…' : run.topic}
      </span>

      <span className="text-drs-muted">•</span>

      <span>
        §<span className="text-drs-accent">{run.currentSection}</span>
        /{run.totalSections}
      </span>

      <span className="text-drs-muted">•</span>

      <span>
        <span style={{ color: budgetColor }}>${run.budgetSpent.toFixed(2)}</span>
        <span className="text-drs-muted">/${run.maxBudget.toFixed(0)}</span>
      </span>

      <span style={{ color: budgetColor }} className="tracking-[0.5px]">{bar} {budgetPct}%</span>

      {run.cssScores && (
        <span className="text-drs-muted text-[11px]">
          CSS{' '}
          <span style={{ color: run.cssScores.content >= 0.65 ? '#22C55E' : '#EF4444' }}>
            C:{run.cssScores.content.toFixed(2)}
          </span>{' '}
          <span style={{ color: run.cssScores.style >= 0.65 ? '#22C55E' : '#EF4444' }}>
            S:{run.cssScores.style.toFixed(2)}
          </span>{' '}
          <span style={{ color: run.cssScores.source >= 0.65 ? '#22C55E' : '#EF4444' }}>
            Src:{run.cssScores.source.toFixed(2)}
          </span>
        </span>
      )}

      <span className="ml-auto flex gap-[8px] items-center">
        <span className="text-[#9CA3AF] text-[11px]">Companion: ready</span>
        <button
          onClick={() => setState('CONVERSING')}
          className="bg-[#202534] text-[#D7DBF0] border border-[#3C435E] rounded-[6px] px-[8px] py-[3px] font-mono text-[11px]"
          title="Apri chat Companion senza interrompere il run"
        >
          Open Companion
        </button>
      </span>
    </div>
  )
}
