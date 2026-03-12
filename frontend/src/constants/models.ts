export interface ModelOption {
  id: string
  name: string
  provider: string
  contextK: number
  costIn: number   // $ per 1M tokens input
  costOut: number  // $ per 1M tokens output
}

export const AVAILABLE_MODELS: ModelOption[] = [
  // Anthropic
  { id: 'anthropic/claude-opus-4-5',   name: 'Claude Opus 4.5',   provider: 'Anthropic', contextK: 200, costIn: 15.0,  costOut: 75.0  },
  { id: 'anthropic/claude-sonnet-4',   name: 'Claude Sonnet 4',   provider: 'Anthropic', contextK: 200, costIn: 3.0,   costOut: 15.0  },
  { id: 'anthropic/claude-haiku-3',    name: 'Claude Haiku 3',    provider: 'Anthropic', contextK: 200, costIn: 0.25,  costOut: 1.25  },
  // OpenAI
  { id: 'openai/o3',                   name: 'o3',                provider: 'OpenAI',    contextK: 200, costIn: 10.0,  costOut: 40.0  },
  { id: 'openai/o3-mini',              name: 'o3-mini',           provider: 'OpenAI',    contextK: 128, costIn: 1.1,   costOut: 4.4   },
  { id: 'openai/gpt-4o',               name: 'GPT-4o',            provider: 'OpenAI',    contextK: 128, costIn: 2.5,   costOut: 10.0  },
  { id: 'openai/gpt-4o-mini',          name: 'GPT-4o Mini',       provider: 'OpenAI',    contextK: 128, costIn: 0.15,  costOut: 0.6   },
  // Google
  { id: 'google/gemini-2.5-pro',       name: 'Gemini 2.5 Pro',    provider: 'Google',    contextK: 1000,costIn: 1.25,  costOut: 5.0   },
  { id: 'google/gemini-2.5-flash',     name: 'Gemini 2.5 Flash',  provider: 'Google',    contextK: 1000,costIn: 0.075, costOut: 0.3   },
  { id: 'google/gemini-1.5-flash',     name: 'Gemini 1.5 Flash',  provider: 'Google',    contextK: 1000,costIn: 0.075, costOut: 0.3   },
  // Perplexity
  { id: 'perplexity/sonar-pro',        name: 'Sonar Pro',         provider: 'Perplexity',contextK: 200, costIn: 3.0,   costOut: 15.0  },
  { id: 'perplexity/sonar',            name: 'Sonar',             provider: 'Perplexity',contextK: 128, costIn: 1.0,   costOut: 1.0   },
  // Meta
  { id: 'meta-llama/llama-3.3-70b-instruct', name: 'Llama 3.3 70B', provider: 'Meta',  contextK: 128, costIn: 0.12,  costOut: 0.3   },
  // Qwen
  { id: 'qwen/qwen3-7b',              name: 'Qwen3 7B',           provider: 'Qwen',      contextK: 32,  costIn: 0.07,  costOut: 0.07  },
]

export const MODELS_BY_PROVIDER: Record<string, ModelOption[]> = AVAILABLE_MODELS.reduce(
  (acc, m) => {
    if (!acc[m.provider]) acc[m.provider] = []
    acc[m.provider].push(m)
    return acc
  },
  {} as Record<string, ModelOption[]>
)
