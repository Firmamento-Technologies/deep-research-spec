// Run & pipeline state types — used by all three Zustand stores and the SSE hook.

export type NodeStatus = 'waiting' | 'running' | 'completed' | 'failed' | 'skipped'

export interface NodeState {
  id: string
  status: NodeStatus
  startedAt?: Date
  completedAt?: Date
  durationMs?: number
  output?: unknown          // raw agent output (summary only, not full payload)
  error?: string
  model?: string
  tokensIn?: number
  tokensOut?: number
  costUsd?: number
}

export type RunStatus =
  | 'initializing'
  | 'running'
  | 'paused'
  | 'awaiting_approval'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type QualityPreset = 'Economy' | 'Balanced' | 'Premium'

export interface CSSScores {
  content: number
  style: number
  source: number
}

export interface JudgeVerdict {
  judgeId: string        // 'r1'|'r2'|'r3'|'f1'|'f2'|'f3'|'s1'|'s2'|'s3'
  pass: boolean
  reasoning?: string
  vetoCategory?: string  // set when judge fires minority veto
}

export interface JuryVerdict {
  sectionIdx: number
  iteration: number
  judges: JudgeVerdict[]
  cssScores: CSSScores
  approved: boolean
  ts: string
}

export interface SectionResult {
  idx: number
  title: string
  content: string
  wordCount: number
  approved: boolean
  iterations: number
  cssScores: CSSScores
  /** Individual CSS scores (flattened for convenience) */
  cssContent?: number
  cssStyle?: number
  cssSource?: number
  /** Computed status derived from pipeline state */
  status?: 'waiting' | 'running' | 'approved' | 'failed'
  /** Alias — some components use wordsCount instead of wordCount */
  wordsCount?: number
  /** Alias — some components use iterationsUsed instead of iterations */
  iterationsUsed?: number
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
  /** Live draft text buffer — appended by DRAFT_CHUNK SSE events */
  liveDraft?: string
  /** HITL (Human-In-The-Loop) payload set by HUMAN_REQUIRED SSE event */
  hitlPayload?: Record<string, unknown>
  /** HITL type: which approval screen to show */
  hitlType?: 'outline_approval' | 'section_approval' | 'escalation'
}
