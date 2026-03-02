// Pipeline canvas types — used by pipeline-layout.ts, pipeline-edges.ts,
// PipelineCanvas, AgentNode, PipelineEdges, PipelineMinimap.

export type NodeCluster =
  | 'setup'
  | 'ingestion'
  | 'mow'
  | 'standard'
  | 'postwrite'
  | 'jury'
  | 'approved'
  | 'reflector'
  | 'panel'
  | 'postqa'
  | 'output'
  | 'shine'
  | 'rlm'

export interface NodeDefinition {
  id: string
  label: string
  x: number           // left position in px on the 2400×3200 canvas
  y: number           // top position in px
  width: number       // default 160
  height: number      // default 56
  cluster: NodeCluster
  model?: string      // default model assigned to this agent
  isSatellite?: boolean    // SHINE/RLM nodes — dashed border, low opacity when inactive
  isHitlGate?: boolean     // diamond shape
  isJuryJudge?: boolean    // circle shape (32px)
  isRouter?: boolean       // triangle shape
}

export type EdgeType = 'solid' | 'dashed' | 'dotted'

export interface EdgeDefinition {
  id: string
  from: string
  to: string
  type: EdgeType      // solid=normal flow, dashed=conditional, dotted=satellite
  label?: string      // condition label shown on dashed edges
  animated?: boolean  // particle animation when source node is running
}
