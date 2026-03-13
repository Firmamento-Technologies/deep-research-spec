import React, { useCallback } from 'react'
import { PIPELINE_NODES, CLUSTER_COLORS } from '../../constants/pipeline-layout'
import { CANVAS_WIDTH, CANVAS_HEIGHT } from './PipelineCanvas'
import type { NodeState } from '../../store/useRunStore'

const MAP_W = 200
const MAP_H = 220
const SCALE_X = MAP_W / CANVAS_WIDTH
const SCALE_Y = MAP_H / CANVAS_HEIGHT

interface PipelineMinimapProps {
  nodeStates: Record<string, NodeState>
  visibleNodeIds: Set<string>
  viewport: { zoom: number; panX: number; panY: number }
  onMinimapClick: (nx: number, ny: number) => void
}

export function PipelineMinimap({ nodeStates, visibleNodeIds, viewport, onMinimapClick }: PipelineMinimapProps) {
  const { zoom, panX, panY } = viewport

  const handleClick = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      const rect = e.currentTarget.getBoundingClientRect()
      const mx = e.clientX - rect.left
      const my = e.clientY - rect.top
      onMinimapClick(mx / SCALE_X, my / SCALE_Y)
    },
    [onMinimapClick]
  )

  const containerW = typeof window !== 'undefined' ? window.innerWidth : 1200
  const containerH = typeof window !== 'undefined' ? window.innerHeight : 800
  const vpW = (containerW / zoom) * SCALE_X
  const vpH = (containerH / zoom) * SCALE_Y
  const vpX = -panX * SCALE_X
  const vpY = -panY * SCALE_Y

  return (
    <div
      style={{ width: MAP_W, height: MAP_H }}
      className="absolute bottom-4 right-4 bg-drs-s1/90 backdrop-blur-sm border border-drs-border rounded-lg overflow-hidden z-20 shadow-lg"
    >
      <svg width={MAP_W} height={MAP_H} className="cursor-pointer" onClick={handleClick}>
        {/* Node dots — scaled */}
        {PIPELINE_NODES.filter((node) => visibleNodeIds.has(node.id)).map(node => {
          const status = nodeStates[node.id]?.status ?? 'waiting'
          const color = CLUSTER_COLORS[node.cluster]
          const mx = node.x * SCALE_X
          const my = node.y * SCALE_Y
          const w = Math.max(4, node.width * SCALE_X)
          const h = Math.max(3, node.height * SCALE_Y)
          return (
            <rect
              key={node.id}
              x={mx}
              y={my}
              width={w}
              height={h}
              rx={1}
              fill={color}
              opacity={status === 'waiting' ? 0.25 : status === 'running' ? 1 : 0.6}
            />
          )
        })}

        {/* Viewport indicator */}
        <rect
          x={Math.max(0, vpX)}
          y={Math.max(0, vpY)}
          width={Math.min(MAP_W, vpW)}
          height={Math.min(MAP_H, vpH)}
          fill="none"
          stroke="#7C8CFF"
          strokeWidth={1.5}
          opacity={0.5}
          rx={2}
        />
      </svg>
    </div>
  )
}
