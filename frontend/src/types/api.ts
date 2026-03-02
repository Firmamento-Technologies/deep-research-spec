export interface RunCreateRequest {
  topic: string
  target_words: number
  quality_preset: string
  style_profile?: string
  max_budget: number
  output_formats: string[]
  hitl_enabled?: boolean
  citation_style?: string
}

export interface SSEEvent {
  event: string
  data: Record<string, unknown> & { ts: string }
}

export interface CompanionMessage {
  role: 'user' | 'companion'
  content: string
}

export interface CompanionAction {
  type: 'START_RUN' | 'SHOW_SECTION' | 'CANCEL_RUN'
  params: Record<string, unknown>
}

export interface CompanionResponse {
  reply: string
  chips?: { label: string; value: string }[] | null
  action?: CompanionAction | null
}
