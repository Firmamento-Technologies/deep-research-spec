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

// ── Compact layout: canvas 1800×1700, clear vertical flow ──
// Columns: LEFT=200, CENTER=560, RIGHT=920, FAR_RIGHT=1280
// Each phase band is ~200px tall with clear spacing

const C = 560   // center column x
const L = 200   // left column x
const R = 920   // right column x
const FR = 1280 // far-right column x
const W = 160   // standard node width
const H = 52    // standard node height
const JW = 44   // jury judge size
const JH = 44

export const PIPELINE_NODES: NodeDefinition[] = [
  // ═══ PHASE 1: SETUP (y: 40–200) ═══
  { id: 'preflight',        label: 'PREFLIGHT',       x: C - 100, y: 50,  width: W, height: H, cluster: 'setup' },
  { id: 'budget_estimator', label: 'BUDGET EST.',     x: C + 100, y: 50,  width: W, height: H, cluster: 'setup' },
  { id: 'planner',          label: 'PLANNER',          x: C,       y: 130, width: W, height: H, cluster: 'setup', model: 'google/gemini-2.5-pro' },
  { id: 'await_outline',    label: 'AWAIT\nOUTLINE',  x: C,       y: 210, width: W, height: H, cluster: 'setup', isHitlGate: true },

  // ═══ PHASE 2: INGESTION (y: 290–530) ═══
  { id: 'researcher',        label: 'RESEARCHER',       x: C,       y: 300, width: W, height: H, cluster: 'ingestion', model: 'perplexity/sonar-pro' },
  { id: 'citation_manager',  label: 'CITATION MGR',    x: C,       y: 370, width: W, height: H, cluster: 'ingestion' },
  { id: 'citation_verifier', label: 'CITATION VER',    x: C,       y: 440, width: W, height: H, cluster: 'ingestion' },
  { id: 'source_sanitizer',  label: 'SRC SANITIZER',   x: C - 100, y: 510, width: W, height: H, cluster: 'ingestion' },
  { id: 'source_synth',      label: 'SRC SYNTH',       x: C + 100, y: 510, width: W, height: H, cluster: 'ingestion', model: 'anthropic/claude-sonnet-4' },

  // ═══ PHASE 3: DRAFTING (y: 600–720) ═══
  // MoW writers — 3 side by side
  { id: 'writer_a',      label: 'WRITER A\nCoverage', x: L,       y: 610, width: W, height: H, cluster: 'mow', model: 'anthropic/claude-opus-4-5' },
  { id: 'writer_b',      label: 'WRITER B\nArgument', x: L + 200, y: 610, width: W, height: H, cluster: 'mow', model: 'anthropic/claude-opus-4-5' },
  { id: 'writer_c',      label: 'WRITER C\nReadab.',  x: L + 400, y: 610, width: W, height: H, cluster: 'mow', model: 'anthropic/claude-opus-4-5' },
  { id: 'writer_single', label: 'WRITER\nSINGLE',     x: R,       y: 610, width: W, height: H, cluster: 'standard', model: 'anthropic/claude-opus-4-5' },

  // MoW merge
  { id: 'jury_multidraft', label: 'JURY MULTI',  x: L + 200, y: 700, width: W, height: H, cluster: 'mow' },
  { id: 'fusor',           label: 'FUSOR',         x: L + 200, y: 770, width: W, height: H, cluster: 'mow', model: 'openai/o3' },

  // ═══ PHASE 4: POST-WRITE (y: 840–1020) ═══
  { id: 'post_draft_analyzer', label: 'POST DRAFT',    x: C,       y: 850,  width: W, height: H, cluster: 'postwrite', model: 'google/gemini-2.5-flash' },
  { id: 'researcher_targeted', label: 'RESEARCHER\nTARGETED', x: R, y: 850, width: W, height: H, cluster: 'postwrite', model: 'perplexity/sonar-pro' },
  { id: 'style_linter',        label: 'STYLE LINTER',  x: C,       y: 930,  width: W, height: H, cluster: 'postwrite' },
  { id: 'style_fixer',         label: 'STYLE FIXER',   x: R,       y: 930,  width: W, height: H, cluster: 'postwrite', model: 'anthropic/claude-sonnet-4' },
  { id: 'metrics_collector',   label: 'METRICS',        x: C,       y: 1010, width: W, height: H, cluster: 'postwrite' },
  { id: 'budget_controller',   label: 'BUDGET CTRL',   x: C,       y: 1080, width: W, height: H, cluster: 'postwrite' },

  // ═══ PHASE 5: JURY SYSTEM (y: 1160–1370) ═══
  { id: 'jury', label: 'JURY DISPATCH', x: C, y: 1160, width: W, height: H, cluster: 'jury' },

  // 9 judges in a compact 3×3 grid
  { id: 'r1', label: 'R1',  x: L + 60,  y: 1240, width: JW, height: JH, cluster: 'jury', isJuryJudge: true, model: 'openai/o3' },
  { id: 'r2', label: 'R2',  x: L + 120, y: 1240, width: JW, height: JH, cluster: 'jury', isJuryJudge: true, model: 'openai/o3-mini' },
  { id: 'r3', label: 'R3',  x: L + 180, y: 1240, width: JW, height: JH, cluster: 'jury', isJuryJudge: true, model: 'openai/o3-mini' },
  { id: 'f1', label: 'F1',  x: C - 30,  y: 1240, width: JW, height: JH, cluster: 'jury', isJuryJudge: true, model: 'google/gemini-2.5-pro' },
  { id: 'f2', label: 'F2',  x: C + 30,  y: 1240, width: JW, height: JH, cluster: 'jury', isJuryJudge: true, model: 'google/gemini-2.5-pro' },
  { id: 'f3', label: 'F3',  x: C + 90,  y: 1240, width: JW, height: JH, cluster: 'jury', isJuryJudge: true, model: 'google/gemini-2.5-pro' },
  { id: 's1', label: 'S1',  x: R - 60,  y: 1240, width: JW, height: JH, cluster: 'jury', isJuryJudge: true, model: 'anthropic/claude-sonnet-4' },
  { id: 's2', label: 'S2',  x: R,       y: 1240, width: JW, height: JH, cluster: 'jury', isJuryJudge: true, model: 'anthropic/claude-haiku-3' },
  { id: 's3', label: 'S3',  x: R + 60,  y: 1240, width: JW, height: JH, cluster: 'jury', isJuryJudge: true, model: 'anthropic/claude-haiku-3' },

  { id: 'aggregator', label: 'AGGREGATOR', x: C, y: 1320, width: W, height: H, cluster: 'jury' },

  // ═══ PHASE 6: ROUTING (y: 1400–1560) ═══
  // Approved path — center
  { id: 'context_compressor', label: 'CTX COMPRESS',    x: C,  y: 1410, width: W, height: H, cluster: 'approved', model: 'qwen/qwen3-7b' },
  { id: 'coherence_guard',    label: 'COHERENCE',        x: C,  y: 1480, width: W, height: H, cluster: 'approved', model: 'google/gemini-2.5-flash' },
  { id: 'section_checkpoint', label: 'SECTION CKPT',    x: C,  y: 1550, width: W, height: H, cluster: 'approved' },

  // Reflector path — right
  { id: 'reflector',    label: 'REFLECTOR',    x: R,      y: 1410, width: W, height: H, cluster: 'reflector', model: 'openai/o3' },
  { id: 'span_editor',  label: 'SPAN EDITOR',  x: R,      y: 1490, width: W, height: H, cluster: 'reflector', model: 'anthropic/claude-sonnet-4' },
  { id: 'diff_merger',  label: 'DIFF MERGER',  x: R,      y: 1570, width: W, height: H, cluster: 'reflector' },
  { id: 'await_human',  label: 'AWAIT\nHUMAN', x: FR,     y: 1490, width: W, height: H, cluster: 'reflector', isHitlGate: true },

  // Panel path — left
  { id: 'panel_discussion', label: 'PANEL DISC.', x: L, y: 1410, width: W, height: H, cluster: 'panel' },

  // ═══ PHASE 7: FINALIZATION (y: 1640–1800) ═══
  { id: 'post_qa',         label: 'POST QA',       x: C,       y: 1650, width: W, height: H, cluster: 'postqa' },
  { id: 'length_adjuster', label: 'LENGTH ADJ.',   x: C + 200, y: 1650, width: W, height: H, cluster: 'postqa' },
  { id: 'publisher',       label: 'PUBLISHER',      x: C,       y: 1740, width: W, height: H, cluster: 'output' },
  { id: 'feedback_collector', label: 'FEEDBACK',    x: C + 200, y: 1740, width: W, height: H, cluster: 'output' },

  // ═══ SATELLITES (far right) ═══
  { id: 'shine_singleton',    label: 'SHINE',         x: FR, y: 610,  width: 140, height: H, cluster: 'shine', isSatellite: true },
  { id: 'shine_hypernetwork', label: 'HYPERNET',     x: FR, y: 680,  width: 140, height: H, cluster: 'shine', isSatellite: true },
  { id: 'shine_lora',         label: 'LORA',          x: FR, y: 750,  width: 140, height: H, cluster: 'shine', isSatellite: true },
  { id: 'rlm_adapter',        label: 'RLM ADAPT.',   x: FR, y: 1160, width: 140, height: H, cluster: 'rlm', isSatellite: true },
  { id: 'deep_research_lm',   label: 'DEEP RES. LM', x: FR, y: 1230, width: 140, height: H, cluster: 'rlm', isSatellite: true },
  { id: 'section_budget_guard',label: 'SEC. BUDGET',  x: FR, y: 1300, width: 140, height: H, cluster: 'rlm', isSatellite: true },
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

// Visual cluster groupings for rendering backgrounds
export interface ClusterGroup {
  id: string
  label: string
  color: string
  x: number
  y: number
  width: number
  height: number
}

export const CLUSTER_GROUPS: ClusterGroup[] = [
  { id: 'g-setup',      label: '1. Setup & Planning',       color: '#4F6EF7', x: 380, y: 20,   width: 460, height: 260 },
  { id: 'g-ingestion',  label: '2. Research & Ingestion',   color: '#06B6D4', x: 380, y: 270,  width: 460, height: 310 },
  { id: 'g-drafting',   label: '3. Multi-Writer Drafting',  color: '#4F6EF7', x: 120, y: 580,  width: 900, height: 230 },
  { id: 'g-postwrite',  label: '4. Post-Write Analysis',    color: '#EC4899', x: 380, y: 820,  width: 780, height: 330 },
  { id: 'g-jury',       label: '5. Jury Evaluation',        color: '#A855F7', x: 120, y: 1130, width: 960, height: 240 },
  { id: 'g-routing',    label: '6. Verdict Routing',        color: '#F97316', x: 120, y: 1380, width: 1340, height: 220 },
  { id: 'g-final',      label: '7. Finalization & Output',  color: '#EAB308', x: 380, y: 1610, width: 600, height: 200 },
]
