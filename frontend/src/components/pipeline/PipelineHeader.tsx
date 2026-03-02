import React from 'react'
import { RunState } from '../../store/useRunStore'

interface PipelineHeaderProps {
  run: RunState | null
}

export function PipelineHeader({ run }: PipelineHeaderProps) {
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
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 10,
        background: 'rgba(10,11,15,0.85)',
        borderBottom: '1px solid #2A2D3A',
        padding: '6px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        fontSize: 12,
        fontFamily: 'monospace',
        color: '#F0F1F6',
        backdropFilter: 'blur(4px)',
        flexWrap: 'wrap',
      }}
    >
      <span style={{ color: '#7C8CFF', fontWeight: 600 }}>
        {run.topic.length > 40 ? run.topic.slice(0, 40) + '…' : run.topic}
      </span>

      <span style={{ color: '#8B8FA8' }}>•</span>

      <span>
        §<span style={{ color: '#7C8CFF' }}>{run.currentSection}</span>
        /{run.totalSections}
      </span>

      <span style={{ color: '#8B8FA8' }}>•</span>

      <span>
        <span style={{ color: budgetColor }}>${run.budgetSpent.toFixed(2)}</span>
        <span style={{ color: '#8B8FA8' }}>/${run.maxBudget.toFixed(0)}</span>
      </span>

      <span style={{ color: budgetColor, letterSpacing: '0.5px' }}>{bar} {budgetPct}%</span>

      {/* CSS Scores */}
      {run.cssScores && (
        <span style={{ color: '#8B8FA8', fontSize: 11 }}>
          CSS{' '}
          <span style={{ color: run.cssScores.content >= 0.65 ? '#22C55E' : '#EF4444' }}>
            C:{run.cssScores.content.toFixed(2)}
          </span>{' '}
          <span style={{ color: run.cssScores.style >= 0.80 ? '#22C55E' : '#EF4444' }}>
            S:{run.cssScores.style.toFixed(2)}
          </span>
        </span>
      )}

      {/* Hard stop banner */}
      {run.hardStopFired && (
        <span
          style={{
            background: '#F97316',
            color: '#0A0B0F',
            padding: '2px 8px',
            borderRadius: 4,
            fontWeight: 700,
            fontSize: 11,
          }}
        >
          ⚠ HARD STOP
        </span>
      )}

      {/* Oscillation badge */}
      {run.oscillationDetected && (
        <span
          style={{
            background: '#EAB30820',
            border: '1px solid #EAB308',
            color: '#EAB308',
            padding: '2px 8px',
            borderRadius: 4,
            fontSize: 11,
          }}
        >
          ⚠️ OSCILLAZIONE {run.oscillationType ? `[${run.oscillationType}]` : ''}
        </span>
      )}
    </div>
  )
}
