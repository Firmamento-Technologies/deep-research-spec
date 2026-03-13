import { NodeDefinition, CLUSTER_COLORS } from '../../constants/pipeline-layout'
import type { NodeState } from '../../store/useRunStore'

interface AgentNodeProps {
  definition: NodeDefinition
  state?: NodeState
  isSelected: boolean
  onClick: () => void
}

const STATUS_COLORS: Record<string, { dot: string; label: string }> = {
  waiting:   { dot: '#50536A', label: 'WAIT' },
  running:   { dot: '#22C55E', label: 'RUN' },
  completed: { dot: '#4F6EF7', label: 'DONE' },
  failed:    { dot: '#EF4444', label: 'FAIL' },
  skipped:   { dot: '#50536A', label: 'SKIP' },
}

export function AgentNode({ definition, state, isSelected, onClick }: AgentNodeProps) {
  const { id, label, x, y, width, height, cluster, model, isSatellite, isHitlGate, isJuryJudge } = definition
  const status = state?.status ?? 'waiting'
  const clusterColor = CLUSTER_COLORS[cluster]
  const isRunning = status === 'running'
  const isCompleted = status === 'completed'
  const isInactive = isSatellite && status === 'waiting'
  const statusInfo = STATUS_COLORS[status] ?? STATUS_COLORS.waiting

  // ── JURY JUDGE — compact circle ──
  if (isJuryJudge) {
    const size = Math.max(width, height)
    return (
      <div
        data-node={id}
        onClick={onClick}
        className="absolute cursor-pointer select-none flex flex-col items-center justify-center rounded-full transition-all duration-200"
        style={{
          left: x,
          top: y,
          width: size,
          height: size,
          background: isCompleted ? `${clusterColor}30` : `${clusterColor}15`,
          border: `2px solid ${
            isSelected ? '#F0F1F6' : isRunning ? clusterColor : `${clusterColor}60`
          }`,
          opacity: isInactive ? 0.3 : 1,
          boxShadow: isRunning
            ? `0 0 12px ${clusterColor}80, 0 0 24px ${clusterColor}30`
            : isSelected
              ? `0 0 0 2px ${clusterColor}50`
              : 'none',
          animation: isRunning ? 'pulse-glow 1.5s ease-in-out infinite' : 'none',
          ['--node-color' as string]: clusterColor,
        }}
      >
        <span className="text-[11px] font-mono font-bold text-drs-text leading-none">
          {label}
        </span>
        {isRunning && (
          <span className="text-[7px] font-mono mt-0.5" style={{ color: statusInfo.dot }}>
            {statusInfo.label}
          </span>
        )}
      </div>
    )
  }

  // ── HITL GATE — diamond shape ──
  if (isHitlGate) {
    const size = Math.min(width, height)
    return (
      <div
        data-node={id}
        onClick={onClick}
        className="absolute cursor-pointer select-none flex items-center justify-center"
        style={{
          left: x,
          top: y,
          width,
          height,
          opacity: isInactive ? 0.3 : 1,
        }}
      >
        <div
          className="transition-all duration-200"
          style={{
            width: size * 0.72,
            height: size * 0.72,
            background: isRunning ? `${clusterColor}30` : `${clusterColor}15`,
            border: `2px solid ${
              isSelected ? '#F0F1F6' : isRunning ? clusterColor : `${clusterColor}60`
            }`,
            transform: 'rotate(45deg)',
            borderRadius: 4,
            boxShadow: isRunning
              ? `0 0 14px ${clusterColor}80`
              : isSelected
                ? `0 0 0 2px ${clusterColor}50`
                : 'none',
            animation: isRunning ? 'pulse-glow 1.5s ease-in-out infinite' : 'none',
            ['--node-color' as string]: clusterColor,
          }}
        />
        <span className="absolute text-[10px] font-mono text-drs-text text-center whitespace-pre-line pointer-events-none font-semibold leading-tight">
          {label}
        </span>
      </div>
    )
  }

  // ── DEFAULT — rectangle node ──
  const borderColor = isSelected
    ? '#F0F1F6'
    : isRunning
      ? clusterColor
      : isSatellite
        ? `${clusterColor}40`
        : `${clusterColor}50`

  return (
    <div
      data-node={id}
      onClick={onClick}
      className="absolute cursor-pointer select-none flex flex-col items-center justify-center px-2 py-1 rounded-lg transition-all duration-200"
      style={{
        left: x,
        top: y,
        width,
        height,
        background: isCompleted
          ? `${clusterColor}20`
          : isRunning
            ? `${clusterColor}18`
            : `${clusterColor}0C`,
        border: `1.5px ${isSatellite ? 'dashed' : 'solid'} ${borderColor}`,
        opacity: isInactive ? 0.25 : 1,
        boxShadow: isRunning
          ? `0 0 10px ${clusterColor}60, 0 0 28px ${clusterColor}25`
          : isSelected
            ? `0 0 0 2px ${clusterColor}40`
            : `0 1px 3px rgba(0,0,0,0.3)`,
        animation: isRunning ? 'pulse-glow 1.5s ease-in-out infinite' : 'none',
        ['--node-color' as string]: clusterColor,
      }}
    >
      {/* Status indicator — top-right */}
      <div className="absolute -top-1 -right-1 flex items-center gap-1">
        <div
          className="w-2 h-2 rounded-full"
          style={{
            background: statusInfo.dot,
            boxShadow: isRunning ? `0 0 6px ${statusInfo.dot}` : 'none',
          }}
        />
      </div>

      {/* Label */}
      <span className="text-[11px] font-mono text-drs-text text-center whitespace-pre-line leading-tight font-medium">
        {label}
      </span>

      {/* Model badge */}
      {model && (isRunning || isSelected) && (
        <span
          className="text-[8px] font-mono mt-0.5 max-w-full overflow-hidden text-ellipsis whitespace-nowrap px-1 rounded"
          style={{
            color: `${clusterColor}CC`,
            background: `${clusterColor}15`,
          }}
        >
          {model.split('/')[1] ?? model}
        </span>
      )}
    </div>
  )
}
