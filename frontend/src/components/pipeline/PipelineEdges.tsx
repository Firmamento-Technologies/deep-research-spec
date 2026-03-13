import { useMemo } from 'react'
import { PIPELINE_EDGES } from '../../constants/pipeline-edges'
import { PIPELINE_NODES, CLUSTER_COLORS, NodeDefinition } from '../../constants/pipeline-layout'
import { CANVAS_WIDTH, CANVAS_HEIGHT } from './PipelineCanvas'
import type { NodeState } from '../../store/useRunStore'

interface PipelineEdgesProps {
  nodeStates: Record<string, NodeState>
  visibleNodeIds: Set<string>
  showLabels: boolean
}

function getNodeCenter(node: NodeDefinition) {
  return {
    x: node.x + node.width / 2,
    y: node.y + node.height / 2,
  }
}

// Reuse arrow markers by color to reduce SVG defs from 110 to ~13
function getColorKey(color: string) {
  return color.replace('#', 'c')
}

export function PipelineEdges({ nodeStates, visibleNodeIds, showLabels }: PipelineEdgesProps) {
  const nodeMap = useMemo(() => {
    const map: Record<string, NodeDefinition> = {}
    PIPELINE_NODES.forEach(n => { map[n.id] = n })
    return map
  }, [])

  const visibleEdges = useMemo(
    () => PIPELINE_EDGES.filter((e) => visibleNodeIds.has(e.from) && visibleNodeIds.has(e.to)),
    [visibleNodeIds],
  )

  // Collect unique colors for shared arrow markers
  const uniqueColors = useMemo(() => {
    const colors = new Set<string>()
    visibleEdges.forEach(edge => {
      const fromNode = nodeMap[edge.from]
      if (fromNode) colors.add(CLUSTER_COLORS[fromNode.cluster])
    })
    return Array.from(colors)
  }, [visibleEdges, nodeMap])

  return (
    <svg
      style={{ width: CANVAS_WIDTH, height: CANVAS_HEIGHT }}
      className="absolute top-0 left-0 pointer-events-none overflow-visible"
    >
      <defs>
        {uniqueColors.map(color => (
          <marker
            key={`arrow-${getColorKey(color)}`}
            id={`arrow-${getColorKey(color)}`}
            markerWidth="8"
            markerHeight="8"
            refX="6"
            refY="4"
            orient="auto"
          >
            <path d="M0,1 L0,7 L7,4 z" fill={color} opacity={0.7} />
          </marker>
        ))}
      </defs>

      {visibleEdges.map(edge => {
        const fromNode = nodeMap[edge.from]
        const toNode = nodeMap[edge.to]
        if (!fromNode || !toNode) return null

        const from = getNodeCenter(fromNode)
        const to = getNodeCenter(toNode)
        const color = CLUSTER_COLORS[fromNode.cluster]
        const fromStatus = nodeStates[edge.from]?.status
        const toStatus = nodeStates[edge.to]?.status
        const isActive = fromStatus === 'running' && edge.animated
        const isCompleted = fromStatus === 'completed' && toStatus === 'completed'

        const opacity = edge.type === 'dotted' ? 0.2
          : isActive ? 0.8
          : isCompleted ? 0.5
          : 0.35

        const dx = to.x - from.x
        const dy = to.y - from.y
        let pathD: string

        if (Math.abs(dy) < 15 && Math.abs(dx) > 80) {
          // Horizontal — gentle arc
          const cy = from.y - 30
          pathD = `M ${from.x} ${from.y} Q ${(from.x + to.x) / 2} ${cy} ${to.x} ${to.y}`
        } else if (dy < -20) {
          // Upward — loop around right side
          const offset = Math.min(100, Math.abs(dx) + 60)
          pathD = `M ${from.x} ${from.y} C ${from.x + offset} ${from.y} ${to.x + offset} ${to.y} ${to.x} ${to.y}`
        } else {
          // Downward — smooth S-curve
          const midY1 = from.y + dy * 0.35
          const midY2 = from.y + dy * 0.65
          pathD = `M ${from.x} ${from.y} C ${from.x} ${midY1} ${to.x} ${midY2} ${to.x} ${to.y}`
        }

        const strokeDasharray =
          edge.type === 'dashed' ? '8 4' :
          edge.type === 'dotted' ? '3 5' :
          undefined

        const pathId = `path-${edge.id}`
        const markerId = `arrow-${getColorKey(color)}`

        return (
          <g key={edge.id}>
            <path
              id={pathId}
              d={pathD}
              stroke={color}
              strokeWidth={isActive ? 2 : 1.2}
              strokeDasharray={strokeDasharray}
              fill="none"
              opacity={opacity}
              markerEnd={`url(#${markerId})`}
            />

            {isActive && (
              <circle r="4" fill={color} opacity={0.9}>
                <animateMotion dur="1.8s" repeatCount="indefinite">
                  <mpath href={`#${pathId}`} />
                </animateMotion>
              </circle>
            )}

            {showLabels && edge.label && (
              <g>
                {/* Label background */}
                <rect
                  x={(from.x + to.x) / 2 - edge.label.length * 3.2}
                  y={(from.y + to.y) / 2 - 12}
                  width={edge.label.length * 6.4 + 4}
                  height={14}
                  rx={3}
                  fill="#0A0B0F"
                  opacity={0.85}
                />
                <text
                  x={(from.x + to.x) / 2}
                  y={(from.y + to.y) / 2 - 2}
                  fontSize={9}
                  fontFamily="monospace"
                  fill={color}
                  opacity={0.85}
                  textAnchor="middle"
                  fontWeight="600"
                >
                  {edge.label}
                </text>
              </g>
            )}
          </g>
        )
      })}
    </svg>
  )
}
