// Available OpenRouter models — used by Settings model-assignment rows,
// AgentModelDropdown (STEP 8) and ModelBadge display.

export interface ModelOption {
  id: string        // OpenRouter model ID (e.g. 'anthropic/claude-sonnet-4-6')
  name: string      // Short display name
  provider: string  // Provider group label
}

export const AVAILABLE_MODELS: ModelOption[] = [
  // Anthropic
  { id: 'anthropic/claude-opus-4-6',   name: 'Claude Opus 4.6',   provider: 'Anthropic'   },
  { id: 'anthropic/claude-sonnet-4-6', name: 'Claude Sonnet 4.6', provider: 'Anthropic'   },
  { id: 'anthropic/claude-haiku-3',    name: 'Claude Haiku 3',    provider: 'Anthropic'   },
  // OpenAI
  { id: 'openai/o3',                   name: 'o3',                provider: 'OpenAI'      },
  { id: 'openai/o3-mini',              name: 'o3 mini',           provider: 'OpenAI'      },
  // Google
  { id: 'google/gemini-3.1-pro',       name: 'Gemini 3.1 Pro',   provider: 'Google'      },
  // Perplexity
  { id: 'perplexity/sonar-pro',        name: 'Sonar Pro',         provider: 'Perplexity'  },
  // Qwen
  { id: 'qwen/qwen3-7b',              name: 'Qwen3 7B',          provider: 'Qwen'        },
]

/** Grouped by provider for <optgroup> dropdowns in Settings and AgentModelDropdown. */
export const MODELS_BY_PROVIDER: Record<string, ModelOption[]> = AVAILABLE_MODELS.reduce(
  (acc, m) => {
    ;(acc[m.provider] ??= []).push(m)
    return acc
  },
  {} as Record<string, ModelOption[]>,
)

/** Default model assignments for all agents — from UI_BUILD_PLAN.md Section 7. */
export const DEFAULT_MODEL_ASSIGNMENTS: Record<string, string> = {
  planner:            'google/gemini-3.1-pro',
  researcher:         'perplexity/sonar-pro',
  researcher_targeted:'perplexity/sonar-pro',
  source_synth:       'anthropic/claude-sonnet-4-6',
  writer_a:           'anthropic/claude-opus-4-6',
  writer_b:           'anthropic/claude-opus-4-6',
  writer_c:           'anthropic/claude-opus-4-6',
  writer_single:      'anthropic/claude-opus-4-6',
  fusor:              'openai/o3',
  post_draft_analyzer:'google/gemini-3.1-pro',
  style_fixer:        'anthropic/claude-sonnet-4-6',
  r1:                 'openai/o3',
  r2:                 'openai/o3-mini',
  r3:                 'openai/o3-mini',
  f1:                 'google/gemini-3.1-pro',
  f2:                 'google/gemini-3.1-pro',
  f3:                 'google/gemini-3.1-pro',
  s1:                 'anthropic/claude-sonnet-4-6',
  s2:                 'anthropic/claude-haiku-3',
  s3:                 'anthropic/claude-haiku-3',
  reflector:          'openai/o3',
  span_editor:        'anthropic/claude-sonnet-4-6',
  context_compressor: 'qwen/qwen3-7b',
  coherence_guard:    'google/gemini-3.1-pro',
}
