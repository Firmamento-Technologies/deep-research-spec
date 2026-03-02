import { useRef, useState, useCallback } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'
import { PIPELINE_NODES } from '../../constants/pipeline-layout'
import { AgentNode } from './AgentNode'
import { PipelineEdges } from './PipelineEdges'
import { PipelineMinimap } from './PipelineMinimap'
import { PipelineHeader } from './PipelineHeader'
import { ShineCluster } from './ShineCluster'
import { RlmCluster } from './RlmCluster'

const CANVAS_WIDTH = 2400
const CANVAS_HEIGHT = 3200
const MIN_ZOOM = 0.15
const MAX_ZOOM = 2.0

export function PipelineCanvas() {
  const containerRef = useRef<HTMLDivElement>(null)
  const { state: appState, selectedNodeId, setSelectedNode } = useAppStore()
  const { activeRun } = useRunStore()

  const [zoom, setZoom] = useState(0.35)
  const [panX, setPanX] = useState(-200)
  const [panY, setPanY] = useState(-40)
  const [isDragging, setIsDragging] = useState(false)
  const dragStart = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null)

  const isVisible = appState === 'PROCESSING' || appState === 'AWAITING_HUMAN'

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? 0.9 : 1.1
    setZoom(z => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z * delta)))
  }, [])

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest('[data-node]')) return
    setIsDragging(true)
    dragStart.current = { x: e.clientX, y: e.clientY, panX, panY }
      ; (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }, [panX, panY])

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!isDragging || !dragStart.current) return
    const dx = e.clientX - dragStart.current.x
    const dy = e.clientY - dragStart.current.y
    setPanX(dragStart.current.panX + dx / zoom)
    setPanY(dragStart.current.panY + dy / zoom)
  }, [isDragging, zoom])

  const handlePointerUp = useCallback(() => {
    setIsDragging(false)
    dragStart.current = null
  }, [])

  const handleMinimapClick = useCallback((nx: number, ny: number) => {
    if (!containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    setPanX(-(nx - rect.width / 2 / zoom))
    setPanY(-(ny - rect.height / 2 / zoom))
  }, [zoom])

  const nodeStates = activeRun?.nodes ?? {}

  return (
    <div
      style={{ visibility: isVisible ? 'visible' : 'hidden', position: 'absolute', inset: 0 }}
    >
      <PipelineHeader run={activeRun} />
      <div
        ref={containerRef}
        className={`w-full h-full overflow-hidden relative ${isDragging ? 'cursor-grabbing' : 'cursor-grab'
          }`}
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        <div
          style={{
            transform: `translate(${panX}px, ${panY}px) scale(${zoom})`,
            transformOrigin: '0 0',
            position: 'absolute',
            width: CANVAS_WIDTH,
            height: CANVAS_HEIGHT,
          }}
        >
          <PipelineEdges nodeStates={nodeStates} />

          {PIPELINE_NODES.map(node => (
            <AgentNode
              key={node.id}
              definition={node}
              state={nodeStates[node.id]}
              isSelected={selectedNodeId === node.id}
              onClick={() => setSelectedNode(node.id === selectedNodeId ? null : node.id)}
            />
          ))}

          <ShineCluster active={activeRun?.shineActive ?? false} />
          <RlmCluster active={activeRun?.rlmMode ?? false} />
        </div>

        <PipelineMinimap
          nodeStates={nodeStates}
          viewport={{ zoom, panX, panY }}
          onMinimapClick={handleMinimapClick}
        />
      </div>
    </div>
  )
}
