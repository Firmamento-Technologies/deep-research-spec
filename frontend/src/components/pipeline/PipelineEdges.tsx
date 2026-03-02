import React, { useMemo } from 'react'
import { PIPELINE_EDGES } from '../../constants/pipeline-edges'
import { PIPELINE_NODES, CLUSTER_COLORS, NodeDefinition } from '../../constants/pipeline-layout'
import { NodeState } from '../../store/useRunStore'

const CANVAS_WIDTH = 2400
const CANVAS_HEIGHT = 3200

interface PipelineEdgesProps {
  nodeStates: Record<string, NodeState>
}

function getNodeCenter(node: NodeDefinition) {
  return {
    x: node.x + node.width / 2,
    y: node.y + node.height / 2,
  }
}

export function PipelineEdges({ nodeStates }: PipelineEdgesProps) {
  const nodeMap = useMemo(() => {
    const map: Record<string, NodeDefinition> = {}
    PIPELINE_NODES.forEach(n => { map[n.id] = n })
    return map
  }, [])

  return (
    <svg
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: CANVAS_WIDTH,
        height: CANVAS_HEIGHT,
        pointerEvents: 'none',
        overflow: 'visible',
      }}
    >
      <defs>
        {PIPELINE_EDGES.map(edge => {
          const fromNode = nodeMap[edge.from]
          if (!fromNode) return null
          const color = CLUSTER_COLORS[fromNode.cluster]
          return (
            <marker
              key={`arrow-${edge.id}`}
              id={`arrow-${edge.id}`}
              markerWidth="6"
              markerHeight="6"
              refX="5"
              refY="3"
              orient="auto"
            >
              <path d="M0,0 L0,6 L6,3 z" fill={color} opacity={0.6} />
            </marker>
          )
        })}
      </defs>

      {PIPELINE_EDGES.map(edge => {
        const fromNode = nodeMap[edge.from]
        const toNode = nodeMap[edge.to]
        if (!fromNode || !toNode) return null

        const from = getNodeCenter(fromNode)
        const to = getNodeCenter(toNode)
        const color = CLUSTER_COLORS[fromNode.cluster]
        const fromStatus = nodeStates[edge.from]?.status
        const isActive = fromStatus === 'running' && edge.animated
        const opacity = edge.type === 'dotted' ? 0.35 : 0.55

        // Calculate bezier control points for back-loop edges
        const dx = to.x - from.x
        const dy = to.y - from.y
        let pathD: string

        if (Math.abs(dy) < 10 && Math.abs(dx) > 100) {
          // Horizontal-ish — slight curve
          const cy = from.y - 40
          pathD = `M ${from.x} ${from.y} Q ${(from.x + to.x) / 2} ${cy} ${to.x} ${to.y}`
        } else if (dy < 0) {
          // Back-loop (going upward)
          const offset = 120
          pathD = `M ${from.x} ${from.y} C ${from.x + offset} ${from.y} ${to.x + offset} ${to.y} ${to.x} ${to.y}`
        } else {
          // Normal downward flow
          const cy1 = from.y + dy * 0.4
          const cy2 = from.y + dy * 0.6
          pathD = `M ${from.x} ${from.y} C ${from.x} ${cy1} ${to.x} ${cy2} ${to.x} ${to.y}`
        }

        const strokeDasharray =
          edge.type === 'dashed' ? '6 4' :
          edge.type === 'dotted' ? '2 4' :
          undefined

        const pathId = `path-${edge.id}`

        return (
          <g key={edge.id}>
            <path
              id={pathId}
              d={pathD}
              stroke={color}
              strokeWidth={1.5}
              strokeDasharray={strokeDasharray}
              fill="none"
              opacity={opacity}
              markerEnd={`url(#arrow-${edge.id})`}
            />

            {/* Particle animation when active */}
            {isActive && (
              <circle r="4" fill={color} opacity={0.9}>
                <animateMotion dur="1.5s" repeatCount="indefinite">
                  <mpath href={`#${pathId}`} />
                </animateMotion>
              </circle>
            )}

            {/* Edge label for conditional branches */}
            {edge.label && (
              <text
                x={(from.x + to.x) / 2}
                y={(from.y + to.y) / 2 - 4}
                fontSize={9}
                fontFamily="monospace"
                fill={color}
                opacity={0.7}
                textAnchor="middle"
              >
                {edge.label}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}
