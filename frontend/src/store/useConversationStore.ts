// useConversationStore — chat messages + companion wiring.
// sendMessage() calls POST /api/companion/chat and handles action dispatch.
// Spec: UI_BUILD_PLAN.md Section 6.

import { create } from 'zustand'
import { api } from '../lib/api'
import { useAppStore } from './useAppStore'
import { useRunStore } from './useRunStore'
import type { CompanionChatResponse } from '../types/api'
import type { QualityPreset, RunState } from '../types/run'

export interface Message {
  id: string
  role: 'user' | 'companion'
  content: string
  timestamp: Date
  chips?: { label: string; value: string }[]
}

interface ConversationStore {
  messages: Message[]
  isTyping: boolean
  addMessage: (msg: Message) => void
  setTyping: (v: boolean) => void
  clearMessages: () => void
  sendMessage: (text: string) => Promise<void>
}

/** Build a minimal RunState skeleton from START_RUN action params. */
function buildInitialRunState(
  docId: string,
  params: Record<string, unknown>,
): RunState {
  return {
    docId,
    topic: params.topic as string,
    status: 'initializing',
    qualityPreset: (params.quality_preset as QualityPreset) ?? 'Balanced',
    targetWords: (params.target_words as number) ?? 5_000,
    maxBudget: (params.max_budget as number) ?? 50,
    budgetSpent: 0,
    budgetRemainingPct: 100,
    totalSections: 0,
    currentSection: 0,
    currentIteration: 0,
    nodes: {},
    cssScores: { content: 0, style: 0, source: 0 },
    juryVerdicts: [],
    sections: [],
    shineActive: false,
    rlmMode: false,
    hardStopFired: false,
    oscillationDetected: false,
    forceApprove: false,
    outputPaths: undefined,
  }
}

export const useConversationStore = create<ConversationStore>((set, get) => ({
  messages: [],
  isTyping: false,

  addMessage: (msg) => set((prev) => ({ messages: [...prev.messages, msg] })),
  setTyping: (v) => set({ isTyping: v }),
  clearMessages: () => set({ messages: [] }),

  sendMessage: async (text: string) => {
    // Add user message immediately
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    }
    get().addMessage(userMsg)
    set({ isTyping: true })

    // ── MOCK mode for dev without backend ───────────────────────────────────
    if (import.meta.env.VITE_MOCK_COMPANION === 'true') {
      await new Promise((r) => setTimeout(r, 800))
      get().addMessage({
        id: crypto.randomUUID(),
        role: 'companion',
        content: `[MOCK] Hai scritto: "${text}". Seleziona un preset per continuare.`,
        timestamp: new Date(),
        chips: [
          { label: 'Economy', value: 'Economy' },
          { label: 'Balanced', value: 'Balanced' },
          { label: 'Premium', value: 'Premium' },
        ],
      })
      set({ isTyping: false })
      return
    }

    // ── Real API call ────────────────────────────────────────────────────
    try {
      const appStore = useAppStore.getState()
      const runStore = useRunStore.getState()

      const resp = await api.post<CompanionChatResponse>('/api/companion/chat', {
        message: text,
        conversation_history: get().messages.slice(-10).map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
        })),
        current_run_state: runStore.activeRun ?? undefined,
      })

      // Add companion reply
      get().addMessage({
        id: crypto.randomUUID(),
        role: 'companion',
        content: resp.reply,
        timestamp: new Date(),
        chips: resp.chips?.map((c) => ({ label: c.label, value: c.value })) ?? undefined,
      })

      // ── Handle action ─────────────────────────────────────────────
      const action = resp.action as Record<string, unknown> | null | undefined

      if (action?.type === 'START_RUN') {
        // 1. Create run on backend
        const params = action.params as Record<string, unknown>
        const runResp = await api.post<{ doc_id: string; status: string }>(
          '/api/runs',
          params,
        )

        // 2. Update app state
        appStore.setActiveDocId(runResp.doc_id)
        appStore.setState('PROCESSING')

        // 3. Seed run store (real-time updates come via SSE)
        runStore.setActiveRun(buildInitialRunState(runResp.doc_id, params))

      } else if (action?.type === 'SHOW_SECTION') {
        appStore.setState('REVIEWING')

      } else if (action?.type === 'CANCEL_RUN') {
        const docId =
          (action.docId as string | undefined) ?? appStore.activeDocId
        if (docId) {
          await api.delete(`/api/runs/${docId}`)
          appStore.setActiveDocId(null)
          appStore.setState('CONVERSING')
        }
      }

    } catch (err) {
      console.error('[companion] error:', err)
      const errorMsg = String(err)
      const isAuthError = errorMsg.includes('401') || errorMsg.includes('502') || errorMsg.includes('503') || errorMsg.includes('Authentication') || errorMsg.includes('API_KEY') || errorMsg.includes('not configured')
      get().addMessage({
        id: crypto.randomUUID(),
        role: 'companion',
        content: isAuthError
          ? '⚠️ La chiave API OpenRouter non è configurata o non è valida. Vai in ⚙ Impostazioni per inserire la tua chiave API, oppure configura la variabile OPENROUTER_API_KEY nel file .env e riavvia i container Docker.'
          : 'Mi dispiace, ho riscontrato un problema di connessione. Riprova tra qualche istante.',
        timestamp: new Date(),
      })
    } finally {
      set({ isTyping: false })
    }
  },
}))
