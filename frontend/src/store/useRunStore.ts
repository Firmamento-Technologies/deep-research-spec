// useRunStore — active and completed pipeline run states.
// Updated by the useSSE hook in real-time.

import { create } from 'zustand'
import type { RunState, NodeState, CSSScores } from '../types/run'

// Re-export types so consumers can import from this module
export type { RunState, NodeState, CSSScores }
export type { SectionResult, NodeStatus, RunStatus, QualityPreset, JudgeVerdict, JuryVerdict } from '../types/run'

export interface ActivityEntry {
  id: number
  ts: Date
  icon: string
  text: string
  detail?: string
  color?: string
}

interface RunStore {
  activeRun: RunState | null
  completedRuns: RunState[]
  activityFeed: ActivityEntry[]
  // Core mutations (called by useSSE)
  setActiveRun: (run: RunState) => void
  updateNode: (nodeId: string, update: Partial<NodeState>) => void
  updateBudget: (spent: number, remainingPct: number) => void
  updateCSS: (scores: CSSScores) => void
  approveSection: (sectionIdx: number) => void
  // Oscillation / run-level meta updates
  setOscillation: (detected: boolean, type?: string) => void
  setRunStatus: (status: RunState['status']) => void
  setHardStop: (fired: boolean) => void
  // Live draft streaming
  appendDraftChunk: (chunk: string) => void
  clearDraft: () => void
  // Activity feed
  pushActivity: (icon: string, text: string, detail?: string, color?: string) => void
  clearActivity: () => void
  // Archive
  archiveRun: () => void
}

function patchRun(
  prev: RunStore,
  patch: Partial<RunState>,
): Pick<RunStore, 'activeRun'> {
  if (!prev.activeRun) return { activeRun: null }
  return { activeRun: { ...prev.activeRun, ...patch } }
}

let _activitySeq = 0

export const useRunStore = create<RunStore>((set) => ({
  activeRun: null,
  completedRuns: [],
  activityFeed: [],

  setActiveRun: (run) => set({ activeRun: run, activityFeed: [] }),

  updateNode: (nodeId, update) =>
    set((prev) => {
      if (!prev.activeRun) return prev
      return {
        activeRun: {
          ...prev.activeRun,
          nodes: {
            ...prev.activeRun.nodes,
            [nodeId]: {
              ...(prev.activeRun.nodes[nodeId] ?? { id: nodeId, status: 'waiting' }),
              ...update,
            },
          },
        },
      }
    }),

  updateBudget: (spent, remainingPct) =>
    set((prev) => patchRun(prev, { budgetSpent: spent, budgetRemainingPct: remainingPct })),

  updateCSS: (scores) =>
    set((prev) => patchRun(prev, { cssScores: scores })),

  approveSection: (sectionIdx) =>
    set((prev) => {
      if (!prev.activeRun) return prev
      return {
        activeRun: {
          ...prev.activeRun,
          sections: prev.activeRun.sections.map((s) =>
            s.idx === sectionIdx ? { ...s, approved: true } : s,
          ),
        },
      }
    }),

  setOscillation: (detected, type) =>
    set((prev) => patchRun(prev, { oscillationDetected: detected, oscillationType: type })),

  setRunStatus: (status) =>
    set((prev) => patchRun(prev, { status })),

  setHardStop: (fired) =>
    set((prev) => patchRun(prev, { hardStopFired: fired })),

  appendDraftChunk: (chunk) =>
    set((prev) => {
      if (!prev.activeRun) return prev
      return patchRun(prev, { liveDraft: (prev.activeRun.liveDraft ?? '') + chunk })
    }),

  clearDraft: () =>
    set((prev) => patchRun(prev, { liveDraft: '' })),

  pushActivity: (icon, text, detail, color) =>
    set((prev) => ({
      activityFeed: [...prev.activityFeed, { id: ++_activitySeq, ts: new Date(), icon, text, detail, color }],
    })),

  clearActivity: () => set({ activityFeed: [] }),

  archiveRun: () =>
    set((prev) => {
      if (!prev.activeRun) return prev
      return {
        activeRun: null,
        completedRuns: [prev.activeRun, ...prev.completedRuns],
        activityFeed: [],
      }
    }),
}))
