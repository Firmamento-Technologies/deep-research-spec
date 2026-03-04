// useAppStore — global app state machine.
// State transitions documented in UI_BUILD_PLAN.md Section 3.

import { create } from 'zustand'

export type AppState = 'IDLE' | 'CONVERSING' | 'PROCESSING' | 'AWAITING_HUMAN' | 'REVIEWING'

/**
 * Valid state transitions:
 * IDLE             → CONVERSING       (user sends first message)
 * IDLE             → PROCESSING       (RunWizard submit)
 * CONVERSING       → PROCESSING       (companion emits START_RUN action)
 * PROCESSING       → AWAITING_HUMAN   (SSE: HUMAN_REQUIRED)
 * AWAITING_HUMAN   → PROCESSING       (user completes HITL)
 * PROCESSING       → REVIEWING        (SSE: PIPELINE_DONE)
 * REVIEWING        → CONVERSING       (user types new message)
 */

interface AppStore {
  state:               AppState
  activeDocId:         string | null
  sidebarCollapsed:    boolean
  rightPanelCollapsed: boolean
  selectedNodeId:      string | null
  /** HITL modal type — set by SSE HUMAN_REQUIRED, cleared after resolution */
  hitlType:    'outline_approval' | 'section_approval' | 'escalation' | null
  hitlPayload: unknown
  /** RunWizard modal visibility */
  wizardOpen: boolean

  // Actions
  setState:         (s: AppState) => void
  setActiveDocId:   (id: string | null) => void
  setSelectedNode:  (nodeId: string | null) => void
  toggleSidebar:    () => void
  toggleRightPanel: () => void
  openHitl:         (type: AppStore['hitlType'], payload: unknown) => void
  closeHitl:        () => void
  openWizard:       () => void
  closeWizard:      () => void
}

export const useAppStore = create<AppStore>((set) => ({
  state:               'IDLE',
  activeDocId:         null,
  sidebarCollapsed:    false,
  rightPanelCollapsed: false,
  selectedNodeId:      null,
  hitlType:            null,
  hitlPayload:         null,
  wizardOpen:          false,

  setState:         (s)    => set({ state: s }),
  setActiveDocId:   (id)   => set({ activeDocId: id }),
  setSelectedNode:  (nodeId) => set({ selectedNodeId: nodeId }),
  toggleSidebar:    ()     => set((prev) => ({ sidebarCollapsed:    !prev.sidebarCollapsed })),
  toggleRightPanel: ()     => set((prev) => ({ rightPanelCollapsed: !prev.rightPanelCollapsed })),
  openHitl:  (type, payload) => set({ hitlType: type, hitlPayload: payload }),
  closeHitl: ()              => set({ hitlType: null, hitlPayload: null }),
  openWizard:  () => set({ wizardOpen: true }),
  closeWizard: () => set({ wizardOpen: false }),
}))
