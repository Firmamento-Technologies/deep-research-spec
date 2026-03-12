export interface NodeDefinition {
  id: string
  label: string
  x: number
  y: number
  width: number
  height: number
  cluster:
    | 'setup' | 'ingestion' | 'mow' | 'standard' | 'postwrite'
    | 'jury' | 'approved' | 'reflector' | 'panel' | 'postqa'
    | 'output' | 'shine' | 'rlm'
  model?: string
  isSatellite?: boolean
  isHitlGate?: boolean
  isJuryJudge?: boolean
  isRouter?: boolean
}

export const PIPELINE_NODES: NodeDefinition[] = [
  // FASE A — SETUP (y: 80-300)
  { id: 'preflight',           label: 'PREFLIGHT',        x: 900,  y: 80,   width: 160, height: 56, cluster: 'setup' },
  { id: 'budget_estimator',    label: 'BUDGET EST.',      x: 1100, y: 80,   width: 160, height: 56, cluster: 'setup' },
  { id: 'planner',             label: 'PLANNER',           x: 1000, y: 180,  width: 160, height: 56, cluster: 'setup', model: 'google/gemini-2.5-pro' },
  { id: 'await_outline',       label: 'AWAIT OUTLINE',    x: 1000, y: 280,  width: 160, height: 56, cluster: 'setup', isHitlGate: true },

  // FASE B — INGESTION (y: 380-700)
  { id: 'researcher',          label: 'RESEARCHER',        x: 1000, y: 380,  width: 160, height: 56, cluster: 'ingestion', model: 'perplexity/sonar-pro' },
  { id: 'citation_manager',    label: 'CITATION MGR',     x: 1000, y: 460,  width: 160, height: 56, cluster: 'ingestion' },
  { id: 'citation_verifier',   label: 'CITATION VER',     x: 1000, y: 540,  width: 160, height: 56, cluster: 'ingestion' },
  { id: 'source_sanitizer',    label: 'SRC SANITIZER',    x: 1000, y: 620,  width: 160, height: 56, cluster: 'ingestion' },
  { id: 'source_synth',        label: 'SRC SYNTHESIZER',  x: 1000, y: 700,  width: 160, height: 56, cluster: 'ingestion', model: 'anthropic/claude-sonnet-4' },

  // MOW WRITERS (y: 800) — 3 parallel
  { id: 'writer_a',            label: 'WRITER A\nCoverage', x: 600,  y: 800,  width: 160, height: 56, cluster: 'mow',      model: 'anthropic/claude-opus-4-5' },
  { id: 'writer_b',            label: 'WRITER B\nArgument', x: 800,  y: 800,  width: 160, height: 56, cluster: 'mow',      model: 'anthropic/claude-opus-4-5' },
  { id: 'writer_c',            label: 'WRITER C\nReadab.',  x: 1000, y: 800,  width: 160, height: 56, cluster: 'mow',      model: 'anthropic/claude-opus-4-5' },
  { id: 'writer_single',       label: 'WRITER SINGLE',    x: 1250, y: 800,  width: 160, height: 56, cluster: 'standard', model: 'anthropic/claude-opus-4-5' },

  // POST-WRITE (y: 960-1240)
  { id: 'jury_multidraft',     label: 'JURY MULTIDRAFT',  x: 800,  y: 960,  width: 160, height: 56, cluster: 'mow' },
  { id: 'fusor',               label: 'FUSOR',             x: 800,  y: 1040, width: 160, height: 56, cluster: 'mow',      model: 'openai/o3' },
  { id: 'post_draft_analyzer', label: 'POST DRAFT ANA.',  x: 1000, y: 960,  width: 160, height: 56, cluster: 'postwrite', model: 'google/gemini-2.5-flash' },
  { id: 'researcher_targeted', label: 'RESEARCHER TGT',   x: 1200, y: 960,  width: 160, height: 56, cluster: 'postwrite', model: 'perplexity/sonar-pro' },
  { id: 'style_linter',        label: 'STYLE LINTER',     x: 1000, y: 1060, width: 160, height: 56, cluster: 'postwrite' },
  { id: 'style_fixer',         label: 'STYLE FIXER',      x: 1200, y: 1060, width: 160, height: 56, cluster: 'postwrite', model: 'anthropic/claude-sonnet-4' },
  { id: 'metrics_collector',   label: 'METRICS COLL.',    x: 1000, y: 1160, width: 160, height: 56, cluster: 'postwrite' },
  { id: 'budget_controller',   label: 'BUDGET CTRL',      x: 1000, y: 1240, width: 160, height: 56, cluster: 'postwrite' },

  // JURY SYSTEM (y: 1340-1560)
  { id: 'jury',                label: 'JURY',              x: 1000, y: 1340, width: 160, height: 56, cluster: 'jury' },
  { id: 'r1',                  label: 'R1',                x: 680,  y: 1440, width: 32,  height: 32,  cluster: 'jury', isJuryJudge: true, model: 'openai/o3' },
  { id: 'r2',                  label: 'R2',                x: 740,  y: 1440, width: 32,  height: 32,  cluster: 'jury', isJuryJudge: true, model: 'openai/o3-mini' },
  { id: 'r3',                  label: 'R3',                x: 800,  y: 1440, width: 32,  height: 32,  cluster: 'jury', isJuryJudge: true, model: 'openai/o3-mini' },
  { id: 'f1',                  label: 'F1',                x: 940,  y: 1440, width: 32,  height: 32,  cluster: 'jury', isJuryJudge: true, model: 'google/gemini-2.5-pro' },
  { id: 'f2',                  label: 'F2',                x: 1000, y: 1440, width: 32,  height: 32,  cluster: 'jury', isJuryJudge: true, model: 'google/gemini-2.5-pro' },
  { id: 'f3',                  label: 'F3',                x: 1060, y: 1440, width: 32,  height: 32,  cluster: 'jury', isJuryJudge: true, model: 'google/gemini-2.5-pro' },
  { id: 's1',                  label: 'S1',                x: 1200, y: 1440, width: 32,  height: 32,  cluster: 'jury', isJuryJudge: true, model: 'anthropic/claude-sonnet-4' },
  { id: 's2',                  label: 'S2',                x: 1260, y: 1440, width: 32,  height: 32,  cluster: 'jury', isJuryJudge: true, model: 'anthropic/claude-haiku-3' },
  { id: 's3',                  label: 'S3',                x: 1320, y: 1440, width: 32,  height: 32,  cluster: 'jury', isJuryJudge: true, model: 'anthropic/claude-haiku-3' },
  { id: 'aggregator',          label: 'AGGREGATOR',        x: 1000, y: 1560, width: 160, height: 56, cluster: 'jury' },

  // APPROVED PATH (y: 1660-1820)
  { id: 'context_compressor',  label: 'CTX COMPRESSOR',   x: 1000, y: 1660, width: 160, height: 56, cluster: 'approved', model: 'qwen/qwen3-7b' },
  { id: 'coherence_guard',     label: 'COHERENCE GUARD',  x: 1000, y: 1740, width: 160, height: 56, cluster: 'approved', model: 'google/gemini-2.5-flash' },
  { id: 'section_checkpoint',  label: 'SECTION CKPT',    x: 1000, y: 1820, width: 160, height: 56, cluster: 'approved' },

  // REFLECTOR PATH (y: 1660-1840) — right branch
  { id: 'reflector',           label: 'REFLECTOR',         x: 1400, y: 1660, width: 160, height: 56, cluster: 'reflector', model: 'openai/o3' },
  { id: 'span_editor',         label: 'SPAN EDITOR',       x: 1300, y: 1760, width: 160, height: 56, cluster: 'reflector', model: 'anthropic/claude-sonnet-4' },
  { id: 'diff_merger',         label: 'DIFF MERGER',       x: 1300, y: 1840, width: 160, height: 56, cluster: 'reflector' },
  { id: 'await_human',         label: 'AWAIT HUMAN',       x: 1500, y: 1760, width: 160, height: 56, cluster: 'reflector', isHitlGate: true },

  // PANEL PATH — left branch
  { id: 'panel_discussion',    label: 'PANEL DISC.',       x: 600,  y: 1660, width: 160, height: 56, cluster: 'panel' },

  // POST QA (y: 1940-2040)
  { id: 'post_qa',             label: 'POST QA',           x: 1000, y: 1940, width: 160, height: 56, cluster: 'postqa' },
  { id: 'length_adjuster',     label: 'LENGTH ADJ.',       x: 1000, y: 2040, width: 160, height: 56, cluster: 'postqa' },

  // OUTPUT (y: 2160+)
  { id: 'publisher',           label: 'PUBLISHER',         x: 1000, y: 2160, width: 160, height: 56, cluster: 'output' },
  { id: 'feedback_collector',  label: 'FEEDBACK COLL.',   x: 1200, y: 2240, width: 160, height: 56, cluster: 'output' },

  // SHINE SATELLITE (right side, y: 800-960)
  { id: 'shine_singleton',     label: 'SHINE SINGLETON',   x: 1700, y: 800,  width: 160, height: 56, cluster: 'shine', isSatellite: true },
  { id: 'shine_hypernetwork',  label: 'SHINE HYPERNET',   x: 1700, y: 880,  width: 160, height: 56, cluster: 'shine', isSatellite: true },
  { id: 'shine_lora',          label: 'LORA WEIGHTS',      x: 1700, y: 960,  width: 160, height: 56, cluster: 'shine', isSatellite: true },

  // RLM SATELLITE (right side, y: 1400-1560)
  { id: 'rlm_adapter',         label: 'RLM ADAPTER',       x: 1700, y: 1400, width: 160, height: 56, cluster: 'rlm', isSatellite: true },
  { id: 'deep_research_lm',    label: 'DEEP RESEARCH LM',  x: 1700, y: 1480, width: 160, height: 56, cluster: 'rlm', isSatellite: true },
  { id: 'section_budget_guard',label: 'SECTION BUDGET',    x: 1700, y: 1560, width: 160, height: 56, cluster: 'rlm', isSatellite: true },
]

export const CLUSTER_COLORS: Record<NodeDefinition['cluster'], string> = {
  setup:      '#4F6EF7',
  ingestion:  '#06B6D4',
  mow:        '#4F6EF7',
  standard:   '#4F6EF7',
  postwrite:  '#EC4899',
  jury:       '#A855F7',
  approved:   '#22C55E',
  reflector:  '#F97316',
  panel:      '#14B8A6',
  postqa:     '#EC4899',
  output:     '#EAB308',
  shine:      '#14B8A6',
  rlm:        '#818CF8',
}
