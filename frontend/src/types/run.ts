export type RunStatus =
  | 'initializing'
  | 'running'
  | 'paused'
  | 'awaiting_approval'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type QualityPreset = 'Economy' | 'Balanced' | 'Premium'

export type HitlType = 'outline_approval' | 'section_approval' | 'escalation'

export interface NodeState {
  id: string
  status: 'waiting' | 'running' | 'completed' | 'failed' | 'skipped'
  startedAt?: string
  completedAt?: string
  durationMs?: number
  output?: unknown
  error?: string
  model?: string
  tokensIn?: number
  tokensOut?: number
  costUsd?: number
}

export interface CSSScores {
  content: number
  style: number
  source: number
}

export interface JuryVerdict {
  judgeId: string // r1 | r2 | r3 | f1 | f2 | f3 | s1 | s2 | s3
  pass: boolean
  cssScore: number
  vetoCategory?: string
  reasoning?: string
  missingEvidence?: string[]
}

export interface Source {
  url: string
  title: string
  reliability: number
  snippet?: string
}

export interface SectionResult {
  idx: number
  title: string
  content: string
  cssScores: CSSScores
  iterations: number
  sources: Source[]
  approvedAt: string
}

export interface RunState {
  docId: string
  topic: string
  status: RunStatus
  qualityPreset: QualityPreset
  targetWords: number
  maxBudget: number
  budgetSpent: number
  budgetRemainingPct: number
  totalSections: number
  currentSection: number
  currentIteration: number
  nodes: Record<string, NodeState>
  cssScores: CSSScores
  juryVerdicts: JuryVerdict[]
  sections: SectionResult[]
  shineActive: boolean
  rlmMode: boolean
  hardStopFired: boolean
  oscillationDetected: boolean
  oscillationType?: string
  forceApprove: boolean
  outputPaths?: Record<string, string>
  createdAt: string
  completedAt?: string
}
