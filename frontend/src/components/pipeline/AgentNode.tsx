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
    position: 'absolute',
    left: x,
    top: y,
    width,
    height,
    cursor: 'pointer',
    userSelect: 'none',
  }

  // JURY JUDGE — circle shape
  if (isJuryJudge) {
    return (
      <div
        data-node={id}
        onClick={onClick}
        style={{
          ...baseStyle,
          width: 32,
          height: 32,
          borderRadius: '50%',
          background: `${clusterColor}22`,
          border: `2px solid ${isSelected ? '#F0F1F6' : isRunning ? clusterColor : `${clusterColor}88`
            }`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
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
        <span style={{ fontSize: 9, fontFamily: 'monospace', color: '#F0F1F6', lineHeight: 1 }}>
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
        style={{
          ...baseStyle,
          width: size,
          height: size,
          background: 'transparent',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
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
        <span
          style={{
            position: 'absolute',
            fontSize: 9,
            fontFamily: 'monospace',
            color: '#F0F1F6',
            textAlign: 'center',
            whiteSpace: 'pre-line',
            pointerEvents: 'none',
          }}
        >
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
        borderRadius: 8,
        borderStyle: isSatellite ? 'dashed' : 'solid',
        opacity: isInactive ? 0.3 : 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '4px 8px',
        boxShadow: isRunning
          ? `0 0 8px ${clusterColor}, 0 0 24px ${clusterColor}40`
          : isSelected
            ? `0 0 0 2px ${clusterColor}60`
            : 'none',
        animation: isRunning ? 'pulse-glow 1.5s ease-in-out infinite' : 'none',
        ['--node-color' as string]: clusterColor,
        transition: 'box-shadow 0.2s, border-color 0.2s, opacity 0.2s',
      }}
    >
      {/* Status dot — top-right */}
      <div
        style={{
          position: 'absolute',
          top: 6,
          right: 6,
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: STATUS_DOT_COLORS[status] ?? '#50536A',
          boxShadow: isRunning ? `0 0 6px ${STATUS_DOT_COLORS['running']}` : 'none',
        }}
      />

      {/* Label */}
      <span
        style={{
          fontSize: 11,
          fontFamily: 'monospace',
          color: '#F0F1F6',
          textAlign: 'center',
          whiteSpace: 'pre-line',
          lineHeight: 1.3,
        }}
      >
        {label}
      </span>

      {/* Model badge — shown when running or selected */}
      {model && (isRunning || isSelected) && (
        <span
          style={{
            fontSize: 8,
            fontFamily: 'monospace',
            color: '#8B8FA8',
            marginTop: 2,
            maxWidth: '100%',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {model.split('/')[1] ?? model}
        </span>
      )}
    </div>
  )
}
