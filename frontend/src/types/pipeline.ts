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
  x: number
  y: number
  width: number
  height: number
  cluster: NodeCluster
  model?: string
  isSatellite?: boolean
  isHitlGate?: boolean
  isJuryJudge?: boolean
  isRouter?: boolean
}

export type EdgeType = 'solid' | 'dashed' | 'dotted'

export interface EdgeDefinition {
  id: string
  from: string
  to: string
  type: EdgeType
  label?: string
  animated?: boolean
}
