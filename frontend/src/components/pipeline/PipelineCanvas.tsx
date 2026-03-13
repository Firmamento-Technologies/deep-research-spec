import { useRef, useState, useCallback, useMemo } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'
import { PIPELINE_NODES, CLUSTER_GROUPS } from '../../constants/pipeline-layout'
import { AgentNode } from './AgentNode'
import { PipelineEdges } from './PipelineEdges'
import { PipelineMinimap } from './PipelineMinimap'
import { PipelineHeader } from './PipelineHeader'
import { ShineCluster } from './ShineCluster'
import { RlmCluster } from './RlmCluster'

type GraphMode = 'core' | 'quality' | 'full'

export const CANVAS_WIDTH = 1600
export const CANVAS_HEIGHT = 1900
const MIN_ZOOM = 0.25
const MAX_ZOOM = 2.5

const CORE_NODE_IDS = new Set([
  'preflight', 'budget_estimator', 'planner', 'await_outline',
  'researcher', 'citation_manager', 'citation_verifier', 'source_sanitizer', 'source_synth',
  'writer_single', 'post_draft_analyzer', 'style_linter', 'metrics_collector', 'budget_controller',
  'jury', 'aggregator',
  'context_compressor', 'coherence_guard', 'section_checkpoint',
  'post_qa', 'length_adjuster', 'publisher',
])

const QUALITY_NODE_IDS = new Set([
  ...Array.from(CORE_NODE_IDS),
  'writer_a', 'writer_b', 'writer_c', 'jury_multidraft', 'fusor',
  'r1', 'r2', 'r3', 'f1', 'f2', 'f3', 's1', 's2', 's3',
  'reflector', 'span_editor', 'diff_merger', 'await_human',
  'panel_discussion', 'researcher_targeted', 'style_fixer',
  'feedback_collector',
])

export function PipelineCanvas() {
  const containerRef = useRef<HTMLDivElement>(null)
  const { state: appState, selectedNodeId, setSelectedNode } = useAppStore()
  const { activeRun } = useRunStore()

  const [zoom, setZoom] = useState(0.55)
  const [panX, setPanX] = useState(-80)
  const [panY, setPanY] = useState(-10)
  const [isDragging, setIsDragging] = useState(false)
  const [graphMode, setGraphMode] = useState<GraphMode>('quality')
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
    const delta = e.deltaY > 0 ? 0.92 : 1.08
    setZoom(z => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z * delta)))
  }, [])

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest('[data-node]')) return
    setIsDragging(true)
    dragStart.current = { x: e.clientX, y: e.clientY, panX, panY }
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
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
    <div style={{ visibility: isVisible ? 'visible' : 'hidden' }} className="absolute inset-0" aria-label="Pipeline visualization" role="img">
      <PipelineHeader run={activeRun} />

      {/* Controls bar */}
      <div className="absolute top-[48px] left-[12px] z-[22] flex gap-2 items-center bg-drs-s1/90 backdrop-blur-sm border border-drs-border rounded-lg px-3 py-2 shadow-lg">
        <span className="text-[11px] font-mono text-drs-muted">Vista:</span>
        <div className="flex rounded-md overflow-hidden border border-drs-border">
          {(['core', 'quality', 'full'] as GraphMode[]).map(mode => (
            <button
              key={mode}
              onClick={() => setGraphMode(mode)}
              className={`px-3 py-1 text-[10px] font-mono border-none cursor-pointer transition-colors ${
                graphMode === mode
                  ? 'bg-drs-accent/20 text-drs-accent'
                  : 'bg-drs-s2 text-drs-muted hover:text-drs-text hover:bg-drs-s3'
              }`}
            >
              {mode === 'core' ? 'Core' : mode === 'quality' ? 'Quality' : 'Full'}
            </button>
          ))}
        </div>

        <div className="w-px h-4 bg-drs-border mx-1" />

        <button
          onClick={() => { setZoom(0.55); setPanX(-80); setPanY(-10) }}
          className="bg-drs-s2 text-drs-muted border border-drs-border rounded-md px-2 py-1 text-[10px] font-mono cursor-pointer hover:text-drs-text hover:bg-drs-s3 transition-colors"
        >
          Reset
        </button>

        <span className="text-[10px] font-mono text-drs-faint ml-1">
          {Math.round(zoom * 100)}%
        </span>
      </div>

      {/* Canvas container */}
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
            width: CANVAS_WIDTH,
            height: CANVAS_HEIGHT,
          }}
          className="absolute"
        >
          {/* Cluster group backgrounds */}
          {CLUSTER_GROUPS.map((group) => (
            <div
              key={group.id}
              style={{
                left: group.x,
                top: group.y,
                width: group.width,
                height: group.height,
              }}
              className="absolute rounded-xl pointer-events-none"
            >
              {/* Background fill */}
              <div
                className="absolute inset-0 rounded-xl"
                style={{
                  background: `${group.color}08`,
                  border: `1px solid ${group.color}25`,
                }}
              />
              {/* Phase label */}
              <div
                className="absolute -top-px left-3 px-2 py-0.5 rounded-b-md"
                style={{
                  background: `${group.color}18`,
                  borderLeft: `1px solid ${group.color}30`,
                  borderRight: `1px solid ${group.color}30`,
                  borderBottom: `1px solid ${group.color}30`,
                }}
              >
                <span
                  className="text-[11px] font-mono font-semibold tracking-wide"
                  style={{ color: `${group.color}CC` }}
                >
                  {group.label}
                </span>
              </div>
            </div>
          ))}

          {/* Edges (SVG layer) */}
          <PipelineEdges nodeStates={nodeStates} visibleNodeIds={visibleNodeIds} showLabels={zoom >= 0.45} />

          {/* Nodes */}
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
