// stream.ts — types for the useRunStream hook.
// ActivityEntry is the log unit consumed by PipelineTimeline.
// StreamEvent is the raw SSE envelope from the backend.

export type RunPhase =
  | 'idle'
  | 'preflight'
  | 'planning'
  | 'researching'
  | 'writing'
  | 'jury'
  | 'reflecting'
  | 'compressing'
  | 'publishing'
  | 'done'
  | 'failed'

export type ActivityEntryType =
  | 'node_started'
  | 'node_completed'
  | 'thinking'
  | 'section_started'
  | 'section_approved'
  | 'jury_pass'
  | 'jury_fail'
  | 'reflector'
  | 'budget'
  | 'human_required'
  | 'warning'
  | 'error'
  | 'system'
  | 'done'

export interface ActivityEntry {
  /** Stable UUID for React key */
  id:    string
  ts:    Date
  type:  ActivityEntryType
  /** Human-readable Italian label shown in the timeline */
  label: string
  /** Which backend node emitted this (if applicable) */
  node?: string
  phase: RunPhase
  /** Extra structured data for rich display (css, cost, iteration…) */
  meta?: Record<string, unknown>
}

export interface StreamEvent {
  event: string
  data:  Record<string, unknown>
}

export const PHASE_LABEL: Record<RunPhase, string> = {
  idle:        'In attesa',
  preflight:   'Controllo modelli',
  planning:    'Pianificazione outline',
  researching: 'Ricerca fonti',
  writing:     'Scrittura sezione',
  jury:        'Giuria in valutazione',
  reflecting:  'Reflector — analisi feedback',
  compressing: 'Compressione contesto',
  publishing:  'Pubblicazione documento',
  done:        'Completato',
  failed:      'Errore',
}

/** Maps backend node IDs to UI phases */
export const NODE_PHASE_MAP: Record<string, RunPhase> = {
  preflight:            'preflight',
  planner:              'planning',
  budget_estimator:     'planning',
  style_calibration:    'planning',
  researcher:           'researching',
  citation_manager:     'researching',
  citation_verifier:    'researching',
  source_sanitizer:     'researching',
  source_synthesizer:   'researching',
  post_draft_analyzer:  'researching',
  writer:               'writing',
  writer_wa:            'writing',
  writer_wb:            'writing',
  writer_wc:            'writing',
  fusor:                'writing',
  span_editor:          'writing',
  diff_merger:          'writing',
  style_fixer:          'writing',
  metrics_collector:    'jury',
  style_linter:         'jury',
  jury:                 'jury',
  jury_multidraft:      'jury',
  aggregator:           'jury',
  panel_discussion:     'jury',
  reflector:            'reflecting',
  oscillation_detector: 'reflecting',
  writer_memory:        'reflecting',
  context_compressor:   'compressing',
  coherence_guard:      'compressing',
  section_checkpoint:   'compressing',
  publisher:            'publishing',
  run_companion:        'idle',
}
