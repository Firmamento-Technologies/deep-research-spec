import React from 'react'
import { NodeDefinition, CLUSTER_COLORS } from '../../constants/pipeline-layout'
import type { NodeState } from '../../store/useRunStore'

interface AgentNodeProps {
  definition: NodeDefinition
  state?: NodeState
  isSelected: boolean
  onClick: () => void
}

const STATUS_DOT_COLORS: Record<string, string> = {
  waiting: '#50536A',
  running: '#22C55E',
  completed: '#4F6EF7',
  failed: '#EF4444',
  skipped: '#50536A',
}

export function AgentNode({ definition, state, isSelected, onClick }: AgentNodeProps) {
  const { id, label, x, y, width, height, cluster, model, isSatellite, isHitlGate, isJuryJudge } = definition
  const status = state?.status ?? 'waiting'
  const clusterColor = CLUSTER_COLORS[cluster]
  const isRunning = status === 'running'
  const isInactive = isSatellite && status === 'waiting'

  const baseStyle: React.CSSProperties = {
    left: x,
    top: y,
    width,
    height,
  }

  // JURY JUDGE — circle shape
  if (isJuryJudge) {
    return (
      <div
        data-node={id}
        onClick={onClick}
        className="absolute cursor-pointer select-none flex items-center justify-center rounded-full"
        style={{
          ...baseStyle,
          width: 32,
          height: 32,
          background: `${clusterColor}22`,
          border: `2px solid ${isSelected ? '#F0F1F6' : isRunning ? clusterColor : `${clusterColor}88`
            }`,
          opacity: isInactive ? 0.3 : 1,
          boxShadow: isRunning
            ? `0 0 10px ${clusterColor}, 0 0 20px ${clusterColor}40`
            : isSelected
              ? `0 0 0 2px ${clusterColor}80`
              : 'none',
          animation: isRunning ? 'pulse-glow 1.5s ease-in-out infinite' : 'none',
          ['--node-color' as string]: clusterColor,
        }}
      >
        <span className="text-[9px] font-mono text-drs-text leading-none">
          {label}
        </span>
      </div>
    )
  }

  // HITL GATE — diamond shape
  if (isHitlGate) {
    const size = Math.min(width, height)
    return (
      <div
        data-node={id}
        onClick={onClick}
        className="absolute cursor-pointer select-none flex items-center justify-center bg-transparent"
        style={{
          ...baseStyle,
          width: size,
          height: size,
          opacity: isInactive ? 0.3 : 1,
        }}
      >
        <div
          style={{
            width: size * 0.7,
            height: size * 0.7,
            background: `${clusterColor}22`,
            border: `2px solid ${isSelected ? '#F0F1F6' : isRunning ? clusterColor : `${clusterColor}88`
              }`,
            transform: 'rotate(45deg)',
            boxShadow: isRunning ? `0 0 10px ${clusterColor}` : 'none',
            animation: isRunning ? 'pulse-glow 1.5s ease-in-out infinite' : 'none',
            ['--node-color' as string]: clusterColor,
          }}
        />
        <span className="absolute text-[9px] font-mono text-drs-text text-center whitespace-pre-line pointer-events-none">
          {label}
        </span>
      </div>
    )
  }

  // DEFAULT — rectangle
  return (
    <div
      data-node={id}
      onClick={onClick}
      className="absolute cursor-pointer select-none flex flex-col items-center justify-center px-[8px] py-[4px] rounded-card transition-[box-shadow,border-color,opacity] duration-200"
      style={{
        ...baseStyle,
        background: `${clusterColor}15`,
        border: `1px solid ${isSelected
            ? '#F0F1F6'
            : isRunning
              ? clusterColor
              : isSatellite
                ? `${clusterColor}55`
                : `${clusterColor}66`
          }`,
        borderStyle: isSatellite ? 'dashed' : 'solid',
        opacity: isInactive ? 0.3 : 1,
        boxShadow: isRunning
          ? `0 0 8px ${clusterColor}, 0 0 24px ${clusterColor}40`
          : isSelected
            ? `0 0 0 2px ${clusterColor}60`
            : 'none',
        animation: isRunning ? 'pulse-glow 1.5s ease-in-out infinite' : 'none',
        ['--node-color' as string]: clusterColor,
      }}
    >
      {/* Status dot — top-right */}
      <div
        className="absolute top-[6px] right-[6px] w-[8px] h-[8px] rounded-full"
        style={{
          background: STATUS_DOT_COLORS[status] ?? '#50536A',
          boxShadow: isRunning ? `0 0 6px ${STATUS_DOT_COLORS['running']}` : 'none',
        }}
      />

      {/* Label */}
      <span className="text-[11px] font-mono text-drs-text text-center whitespace-pre-line leading-[1.3]">
        {label}
      </span>

      {/* Model badge — shown when running or selected */}
      {model && (isRunning || isSelected) && (
        <span className="text-[8px] font-mono text-drs-muted mt-[2px] max-w-full overflow-hidden text-ellipsis whitespace-nowrap">
          {model.split('/')[1] ?? model}
        </span>
      )}
    </div>
  )
}
