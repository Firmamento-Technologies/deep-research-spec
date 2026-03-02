// useConversationStore — chat message history and companion interaction.
// sendMessage is wired to POST /api/companion/chat in STEP 6.
// This file also exports the Message type (used by api.ts).

import { create } from 'zustand'

export interface Message {
  id: string
  role: 'user' | 'companion'
  content: string
  timestamp: Date
  chips?: { label: string; value: string }[]   // optional suggestion chips from companion
}

interface ConversationStore {
  messages: Message[]
  isTyping: boolean
  addMessage: (msg: Message) => void
  setTyping: (v: boolean) => void
  clearMessages: () => void
  /** Dispatches user message and calls the companion API. Full impl in STEP 6. */
  sendMessage: (text: string) => Promise<void>
}

export const useConversationStore = create<ConversationStore>((set, get) => ({
  messages: [],
  isTyping: false,

  addMessage: (msg) =>
    set((prev) => ({ messages: [...prev.messages, msg] })),

  setTyping: (v) => set({ isTyping: v }),

  clearMessages: () => set({ messages: [] }),

  sendMessage: async (text: string) => {
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    }
    get().addMessage(userMsg)
    set({ isTyping: true })
    // POST /api/companion/chat — connected in STEP 6
    // Placeholder: echo back a stub reply during development
    if (import.meta.env.DEV) {
      await new Promise((r) => setTimeout(r, 600))
      get().addMessage({
        id: crypto.randomUUID(),
        role: 'companion',
        content: '[companion stub — collegato in STEP 6]',
        timestamp: new Date(),
      })
    }
    set({ isTyping: false })
  },
}))
