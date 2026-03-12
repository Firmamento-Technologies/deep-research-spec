export interface EdgeDefinition {
  id: string
  from: string
  to: string
  type: 'solid' | 'dashed' | 'dotted'
  label?: string
  animated?: boolean
}

export const PIPELINE_EDGES: EdgeDefinition[] = [
  // FASE A — SETUP
  { id: 'e-preflight-budget',      from: 'preflight',           to: 'budget_estimator',    type: 'solid' },
  { id: 'e-budget-planner',        from: 'budget_estimator',    to: 'planner',             type: 'solid' },
  { id: 'e-planner-outline',       from: 'planner',             to: 'await_outline',       type: 'solid' },
  { id: 'e-outline-researcher',    from: 'await_outline',       to: 'researcher',          type: 'solid' },

  // INGESTION chain
  { id: 'e-researcher-citman',     from: 'researcher',          to: 'citation_manager',    type: 'solid', animated: true },
  { id: 'e-citman-citver',         from: 'citation_manager',    to: 'citation_verifier',   type: 'solid' },
  { id: 'e-citver-srcsan',         from: 'citation_verifier',   to: 'source_sanitizer',    type: 'solid' },
  { id: 'e-srcsan-srcsynth',       from: 'source_sanitizer',    to: 'source_synth',        type: 'solid' },

  // SOURCE SYNTH → WRITERS (conditional branch)
  { id: 'e-srcsynth-writera',      from: 'source_synth',        to: 'writer_a',            type: 'dashed', label: 'MoW' },
  { id: 'e-srcsynth-writerb',      from: 'source_synth',        to: 'writer_b',            type: 'dashed', label: 'MoW' },
  { id: 'e-srcsynth-writerc',      from: 'source_synth',        to: 'writer_c',            type: 'dashed', label: 'MoW' },
  { id: 'e-srcsynth-writersingle', from: 'source_synth',        to: 'writer_single',       type: 'dashed', label: 'Standard' },

  // MoW → JURY MULTIDRAFT → FUSOR
  { id: 'e-writera-jurymulti',     from: 'writer_a',            to: 'jury_multidraft',     type: 'solid', animated: true },
  { id: 'e-writerb-jurymulti',     from: 'writer_b',            to: 'jury_multidraft',     type: 'solid', animated: true },
  { id: 'e-writerc-jurymulti',     from: 'writer_c',            to: 'jury_multidraft',     type: 'solid', animated: true },
  { id: 'e-jurymulti-fusor',       from: 'jury_multidraft',     to: 'fusor',               type: 'solid' },

  // CONVERGE → POST-WRITE
  { id: 'e-fusor-postdraft',       from: 'fusor',               to: 'post_draft_analyzer', type: 'solid' },
  { id: 'e-writersingle-postdraft',from: 'writer_single',       to: 'post_draft_analyzer', type: 'solid' },

  // POST-WRITE chain
  { id: 'e-postdraft-reatgt',      from: 'post_draft_analyzer', to: 'researcher_targeted', type: 'dashed', label: 'gaps' },
  { id: 'e-postdraft-stylelint',   from: 'post_draft_analyzer', to: 'style_linter',        type: 'solid' },
  { id: 'e-reatgt-stylelint',      from: 'researcher_targeted', to: 'style_linter',        type: 'solid' },
  { id: 'e-stylelint-stylefix',    from: 'style_linter',        to: 'style_fixer',         type: 'dashed', label: 'violations' },
  { id: 'e-stylefix-stylelint',    from: 'style_fixer',         to: 'style_linter',        type: 'dashed', label: 'retry' },
  { id: 'e-stylelint-metrics',     from: 'style_linter',        to: 'metrics_collector',   type: 'solid' },
  { id: 'e-metrics-budgetctrl',    from: 'metrics_collector',   to: 'budget_controller',   type: 'solid' },
  { id: 'e-budgetctrl-jury',       from: 'budget_controller',   to: 'jury',                type: 'solid' },

  // JURY → JUDGES
  { id: 'e-jury-r1', from: 'jury', to: 'r1', type: 'solid' },
  { id: 'e-jury-r2', from: 'jury', to: 'r2', type: 'solid' },
  { id: 'e-jury-r3', from: 'jury', to: 'r3', type: 'solid' },
  { id: 'e-jury-f1', from: 'jury', to: 'f1', type: 'solid' },
  { id: 'e-jury-f2', from: 'jury', to: 'f2', type: 'solid' },
  { id: 'e-jury-f3', from: 'jury', to: 'f3', type: 'solid' },
  { id: 'e-jury-s1', from: 'jury', to: 's1', type: 'solid' },
  { id: 'e-jury-s2', from: 'jury', to: 's2', type: 'solid' },
  { id: 'e-jury-s3', from: 'jury', to: 's3', type: 'solid' },

  // JUDGES → AGGREGATOR
  { id: 'e-r1-agg', from: 'r1', to: 'aggregator', type: 'solid', animated: true },
  { id: 'e-r2-agg', from: 'r2', to: 'aggregator', type: 'solid', animated: true },
  { id: 'e-r3-agg', from: 'r3', to: 'aggregator', type: 'solid', animated: true },
  { id: 'e-f1-agg', from: 'f1', to: 'aggregator', type: 'solid', animated: true },
  { id: 'e-f2-agg', from: 'f2', to: 'aggregator', type: 'solid', animated: true },
  { id: 'e-f3-agg', from: 'f3', to: 'aggregator', type: 'solid', animated: true },
  { id: 'e-s1-agg', from: 's1', to: 'aggregator', type: 'solid', animated: true },
  { id: 'e-s2-agg', from: 's2', to: 'aggregator', type: 'solid', animated: true },
  { id: 'e-s3-agg', from: 's3', to: 'aggregator', type: 'solid', animated: true },

  // AGGREGATOR → ROUTING (conditional)
  { id: 'e-agg-ctxcomp',       from: 'aggregator', to: 'context_compressor',  type: 'dashed', label: 'approved' },
  { id: 'e-agg-reflector',     from: 'aggregator', to: 'reflector',           type: 'dashed', label: 'fail/veto' },
  { id: 'e-agg-stylelint2',    from: 'aggregator', to: 'style_linter',        type: 'dashed', label: 'fail_style' },
  { id: 'e-agg-panel',         from: 'aggregator', to: 'panel_discussion',    type: 'dashed', label: 'panel' },
  { id: 'e-agg-reatgt2',       from: 'aggregator', to: 'researcher_targeted', type: 'dashed', label: 'missing_ev' },

  // APPROVED PATH
  { id: 'e-ctxcomp-coherence', from: 'context_compressor', to: 'coherence_guard',    type: 'solid' },
  { id: 'e-coherence-secckpt', from: 'coherence_guard',    to: 'section_checkpoint', type: 'solid' },
  { id: 'e-secckpt-researcher',from: 'section_checkpoint', to: 'researcher',          type: 'dashed', label: 'next_section', animated: true },
  { id: 'e-secckpt-postqa',    from: 'section_checkpoint', to: 'post_qa',             type: 'dashed', label: 'all_done' },

  // REFLECTOR PATH
  { id: 'e-reflector-spaneditor',    from: 'reflector',   to: 'span_editor',    type: 'dashed', label: 'SURGICAL' },
  { id: 'e-reflector-writersingle2', from: 'reflector',   to: 'writer_single',  type: 'dashed', label: 'PARTIAL' },
  { id: 'e-reflector-awaithuman',    from: 'reflector',   to: 'await_human',    type: 'dashed', label: 'FULL' },
  { id: 'e-spaneditor-diffmerger',   from: 'span_editor', to: 'diff_merger',    type: 'solid' },
  { id: 'e-diffmerger-stylelint3',   from: 'diff_merger', to: 'style_linter',   type: 'solid' },
  { id: 'e-awaithuman-writersingle3',from: 'await_human', to: 'writer_single',  type: 'solid' },

  // PANEL PATH
  { id: 'e-panel-agg', from: 'panel_discussion', to: 'aggregator', type: 'solid' },

  // POST QA
  { id: 'e-postqa-publisher',    from: 'post_qa',       to: 'publisher',      type: 'dashed', label: 'ok' },
  { id: 'e-postqa-lengthadj',    from: 'post_qa',       to: 'length_adjuster',type: 'dashed', label: 'length_out' },
  { id: 'e-postqa-awaithuman2',  from: 'post_qa',       to: 'await_human',    type: 'dashed', label: 'conflicts' },
  { id: 'e-lengthadj-publisher', from: 'length_adjuster',to: 'publisher',     type: 'solid' },

  // OUTPUT
  { id: 'e-publisher-feedback', from: 'publisher', to: 'feedback_collector', type: 'dotted' },

  // SATELLITE connections (dotted)
  { id: 'e-shine-writera',  from: 'shine_singleton',     to: 'writer_a',          type: 'dotted' },
  { id: 'e-shine-writerb',  from: 'shine_singleton',     to: 'writer_b',          type: 'dotted' },
  { id: 'e-shine-writerc',  from: 'shine_singleton',     to: 'writer_c',          type: 'dotted' },
  { id: 'e-rlm-jury',       from: 'rlm_adapter',         to: 'jury',              type: 'dotted' },
  { id: 'e-rlm-budget',     from: 'section_budget_guard',to: 'budget_controller', type: 'dotted' },
]
