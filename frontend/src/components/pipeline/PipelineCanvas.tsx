import { useRef, useState, useCallback, useMemo } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'
import { PIPELINE_NODES } from '../../constants/pipeline-layout'
import { AgentNode } from './AgentNode'
import { PipelineEdges } from './PipelineEdges'
import { PipelineMinimap } from './PipelineMinimap'
import { PipelineHeader } from './PipelineHeader'
import { ShineCluster } from './ShineCluster'
import { RlmCluster } from './RlmCluster'

type GraphMode = 'core' | 'quality' | 'full'

const CANVAS_WIDTH = 2400
const CANVAS_HEIGHT = 3200
const MIN_ZOOM = 0.15
const MAX_ZOOM = 2.0

const PHASE_LANES = [
  { label: '1) Setup & Budget', y: 80, h: 340 },
  { label: '2) Ingestion & Research', y: 420, h: 380 },
  { label: '3) Drafting', y: 800, h: 330 },
  { label: '4) Quality Loop (Jury/Reflector/Panel)', y: 1130, h: 820 },
  { label: '5) Finalization & Output', y: 1950, h: 500 },
]

const CORE_NODE_IDS = new Set([
  'starter', 'budget_controller', 'planner', 'section_router', 'researcher',
  'writer_single', 'style_linter', 'aggregator', 'context_compressor',
  'coherence_guard', 'section_checkpoint', 'post_qa', 'length_adjuster', 'publisher',
])

const QUALITY_NODE_IDS = new Set([
  ...Array.from(CORE_NODE_IDS),
  'jury', 'r1', 'f1', 's1', 'reflector', 'span_editor', 'diff_merger',
  'await_human', 'panel_discussion', 'researcher_targeted',
])

export function PipelineCanvas() {
  const containerRef = useRef<HTMLDivElement>(null)
  const { state: appState, selectedNodeId, setSelectedNode } = useAppStore()
  const { activeRun } = useRunStore()

  const [zoom, setZoom] = useState(0.35)
  const [panX, setPanX] = useState(-200)
  const [panY, setPanY] = useState(-40)
  const [isDragging, setIsDragging] = useState(false)
  const [graphMode, setGraphMode] = useState<GraphMode>('core')
  const dragStart = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null)

  const isVisible = appState === 'PROCESSING' || appState === 'AWAITING_HUMAN'

  const visibleNodeIds = useMemo(() => {
    if (graphMode === 'full') return new Set(PIPELINE_NODES.map((n) => n.id))
    if (graphMode === 'quality') return QUALITY_NODE_IDS
    return CORE_NODE_IDS
  }, [graphMode])

  const visibleNodes = useMemo(
    () => PIPELINE_NODES.filter((n) => visibleNodeIds.has(n.id)),
    [visibleNodeIds],
  )

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
    <div style={{ visibility: isVisible ? 'visible' : 'hidden', position: 'absolute', inset: 0 }}>
      <PipelineHeader run={activeRun} />

      <div
        style={{
          position: 'absolute',
          top: 44,
          left: 12,
          zIndex: 22,
          display: 'flex',
          gap: 8,
          alignItems: 'center',
          background: 'rgba(10,11,15,0.8)',
          border: '1px solid #2A2D3A',
          borderRadius: 8,
          padding: '6px 8px',
          color: '#D7DAE8',
          fontSize: 11,
          fontFamily: 'monospace',
        }}
      >
        <span>View:</span>
        <select
          value={graphMode}
          onChange={(e) => setGraphMode(e.target.value as GraphMode)}
          style={{ background: '#151821', color: '#F0F1F6', border: '1px solid #34384A', borderRadius: 4 }}
        >
          <option value="core">Core flow</option>
          <option value="quality">Core + quality loop</option>
          <option value="full">Full architecture</option>
        </select>

        <button
          onClick={() => {
            setZoom(0.35)
            setPanX(-200)
            setPanY(-40)
          }}
          style={{
            background: '#202534', color: '#CDD2EA', border: '1px solid #3A4058', borderRadius: 4, padding: '2px 8px',
          }}
        >
          Reset view
        </button>
      </div>

      <div
        ref={containerRef}
        className={`w-full h-full overflow-hidden relative ${isDragging ? 'cursor-grabbing' : 'cursor-grab'}`}
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
          {PHASE_LANES.map((lane) => (
            <div
              key={lane.label}
              style={{
                position: 'absolute',
                left: 120,
                top: lane.y,
                width: 1800,
                height: lane.h,
                border: '1px solid rgba(92,101,132,0.25)',
                background: 'rgba(30,34,45,0.22)',
                borderRadius: 10,
              }}
            >
              <span style={{ fontSize: 10, color: '#AEB5CF', fontFamily: 'monospace', marginLeft: 8 }}>{lane.label}</span>
            </div>
          ))}

          <PipelineEdges nodeStates={nodeStates} visibleNodeIds={visibleNodeIds} showLabels={zoom >= 0.55} />

          {visibleNodes.map(node => (
            <AgentNode
              key={node.id}
              definition={node}
              state={nodeStates[node.id]}
              isSelected={selectedNodeId === node.id}
              onClick={() => setSelectedNode(node.id === selectedNodeId ? null : node.id)}
            />
          ))}

          {graphMode === 'full' && <ShineCluster active={activeRun?.shineActive ?? false} />}
          {graphMode === 'full' && <RlmCluster active={activeRun?.rlmMode ?? false} />}
        </div>

        <PipelineMinimap
          nodeStates={nodeStates}
          visibleNodeIds={visibleNodeIds}
          viewport={{ zoom, panX, panY }}
          onMinimapClick={handleMinimapClick}
        />
      </div>
    </div>
  )
}
