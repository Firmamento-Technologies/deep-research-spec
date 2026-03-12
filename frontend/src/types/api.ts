// API request/response types and SSE event envelope.
// Mirrors the FastAPI Pydantic models defined in backend/api/.

import type { RunState, QualityPreset, CSSScores } from './run'
import type { Message } from '../store/useConversationStore'

// -------------------------------------------------------
// Run endpoints
// -------------------------------------------------------

export interface RunCreateRequest {
  topic: string
  qualityPreset: QualityPreset
  targetWords: number
  maxBudget: number
  styleProfile?: string
}

export interface RunCreateResponse {
  docId: string
  status: 'initializing'
}

export interface RunListItem {
  docId: string
  topic: string
  status: RunState['status']
  qualityPreset: QualityPreset
  budgetSpent: number
  maxBudget: number
  createdAt: string
  completedAt?: string
}

// -------------------------------------------------------
// Companion chat
// -------------------------------------------------------

export type CompanionAction =
  | { type: 'START_RUN';     params: RunCreateRequest }
  | { type: 'SHOW_SECTION';  sectionIdx: number }
  | { type: 'CANCEL_RUN';    docId: string }

export interface CompanionChatRequest {
  message: string
  conversationHistory: Message[]
  currentRunState?: RunState
}

export interface CompanionChatResponse {
  reply: string
  chips?: { label: string; value: string }[]
  action?: CompanionAction
}

// -------------------------------------------------------
// HITL
// -------------------------------------------------------

export interface ApproveOutlineRequest {
  sections: { title: string; scope: string; targetWords: number }[]
}

export interface ApproveSectionRequest {
  sectionIdx: number
  approved: boolean
  editedContent?: string
}

export type EscalationResolution = 'auto' | 'manual' | 'skip'

export interface ResolveEscalationRequest {
  action: EscalationResolution
  editedContent?: string
}

// -------------------------------------------------------
// Settings
// -------------------------------------------------------

export interface NodeModelOverride {
  nodeId: string
  newModel: string
}

// -------------------------------------------------------
// SSE
// -------------------------------------------------------

export interface SSEEvent {
  event: string
  data: Record<string, unknown> & { ts: string }
}

// Named SSE event payloads (used for type-narrowing in useSSE)
export interface SSENodeStarted   { node: string }
export interface SSENodeCompleted { node: string; duration_s: number; output: unknown }
export interface SSENodeFailed    { node: string; error: string }
export interface SSECSSUpdate     extends CSSScores {}
export interface SSEBudgetUpdate  { spent: number; remaining_pct: number }
export interface SSEHumanRequired { type: 'outline_approval' | 'section_approval' | 'escalation'; payload: unknown }
export interface SSEOscillation   { type: string }
export interface SSEDraftChunk    { node: string; chunk: string }
export interface SSESectionApproved { section_idx: number }
