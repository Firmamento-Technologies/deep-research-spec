import React, { useCallback } from 'react'
import { PIPELINE_NODES, CLUSTER_COLORS } from '../../constants/pipeline-layout'
import type { NodeState } from '../../store/useRunStore'

const CANVAS_WIDTH = 2400
const CANVAS_HEIGHT = 3200
const MAP_W = 160
const MAP_H = 100
const SCALE_X = MAP_W / CANVAS_WIDTH
const SCALE_Y = MAP_H / CANVAS_HEIGHT

interface PipelineMinimapProps {
  nodeStates: Record<string, NodeState>
  viewport: { zoom: number; panX: number; panY: number }
  onMinimapClick: (nx: number, ny: number) => void
}

export function PipelineMinimap({ nodeStates, viewport, onMinimapClick }: PipelineMinimapProps) {
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

  // Viewport rect in minimap coords
  const containerW = typeof window !== 'undefined' ? window.innerWidth : 1200
  const containerH = typeof window !== 'undefined' ? window.innerHeight : 800
  const vpW = (containerW / zoom) * SCALE_X
  const vpH = (containerH / zoom) * SCALE_Y
  const vpX = -panX * SCALE_X
  const vpY = -panY * SCALE_Y

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 16,
        right: 16,
        width: MAP_W,
        height: MAP_H,
        background: '#111318',
        border: '1px solid #2A2D3A',
        borderRadius: 6,
        overflow: 'hidden',
        zIndex: 20,
      }}
    >
      <svg
        width={MAP_W}
        height={MAP_H}
        style={{ cursor: 'pointer' }}
        onClick={handleClick}
      >
        {/* Node dots */}
        {PIPELINE_NODES.map(node => {
          const status = nodeStates[node.id]?.status ?? 'waiting'
          const color = CLUSTER_COLORS[node.cluster]
          const mx = node.x * SCALE_X
          const my = node.y * SCALE_Y
          return (
            <rect
              key={node.id}
              x={mx}
              y={my}
              width={3}
              height={2}
              fill={color}
              opacity={status === 'waiting' ? 0.3 : status === 'running' ? 1 : 0.65}
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
          strokeWidth={1}
          opacity={0.6}
        />
      </svg>
    </div>
  )
}
