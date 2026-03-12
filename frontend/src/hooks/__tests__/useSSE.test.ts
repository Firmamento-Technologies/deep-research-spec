/**
 * Tests for useSSE hook dispatch logic.
 *
 * We test the dispatch behavior by directly calling store actions
 * the same way the SSE hook does, since testing the real EventSource
 * or mock timer mode requires a full rendering environment.
 */
import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'
import type { RunState } from '../../types/run'

function makeRun(): RunState {
  return {
    docId: 'sse-test',
    topic: 'SSE Test',
    status: 'running',
    qualityPreset: 'Balanced',
    targetWords: 8000,
    maxBudget: 50,
    budgetSpent: 0,
    budgetRemainingPct: 100,
    totalSections: 2,
    currentSection: 0,
    currentIteration: 0,
    nodes: {},
    cssScores: { content: 0, style: 0, source: 0 },
    juryVerdicts: [],
    sections: [
      { idx: 0, title: 'S0', content: '', wordCount: 0, approved: false, iterations: 0, cssScores: { content: 0, style: 0, source: 0 } },
    ],
    shineActive: false,
    rlmMode: false,
    hardStopFired: false,
    oscillationDetected: false,
    forceApprove: false,
  }
}

beforeEach(() => {
  useAppStore.setState({
    state: 'PROCESSING',
    activeDocId: 'sse-test',
    sidebarCollapsed: false,
    rightPanelCollapsed: false,
    selectedNodeId: null,
    hitlType: null,
    hitlPayload: null,
  })
  useRunStore.setState({ activeRun: makeRun(), completedRuns: [] })
})

describe('SSE event dispatch logic', () => {
  it('NODE_STARTED sets node to running', () => {
    useRunStore.getState().updateNode('preflight', { status: 'running', startedAt: new Date() })
    expect(useRunStore.getState().activeRun?.nodes['preflight']?.status).toBe('running')
  })

  it('NODE_COMPLETED sets node to completed with metadata', () => {
    useRunStore.getState().updateNode('planner', {
      status: 'completed',
      completedAt: new Date(),
      durationMs: 1500,
      tokensIn: 2000,
      tokensOut: 500,
      costUsd: 0.02,
    })
    const node = useRunStore.getState().activeRun?.nodes['planner']
    expect(node?.status).toBe('completed')
    expect(node?.costUsd).toBe(0.02)
  })

  it('NODE_FAILED sets error on node', () => {
    useRunStore.getState().updateNode('researcher', { status: 'failed', error: 'API timeout' })
    expect(useRunStore.getState().activeRun?.nodes['researcher']?.error).toBe('API timeout')
  })

  it('SECTION_APPROVED marks section', () => {
    useRunStore.getState().approveSection(0)
    expect(useRunStore.getState().activeRun?.sections[0].approved).toBe(true)
  })

  it('CSS_UPDATE updates scores', () => {
    useRunStore.getState().updateCSS({ content: 0.82, style: 0.75, source: 0.88 })
    const scores = useRunStore.getState().activeRun?.cssScores
    expect(scores?.content).toBe(0.82)
    expect(scores?.style).toBe(0.75)
    expect(scores?.source).toBe(0.88)
  })

  it('BUDGET_UPDATE updates budget', () => {
    useRunStore.getState().updateBudget(15.0, 70)
    expect(useRunStore.getState().activeRun?.budgetSpent).toBe(15.0)
    expect(useRunStore.getState().activeRun?.budgetRemainingPct).toBe(70)
  })

  it('HUMAN_REQUIRED transitions app to AWAITING_HUMAN and opens HITL', () => {
    useAppStore.getState().setState('AWAITING_HUMAN')
    useAppStore.getState().openHitl('outline_approval', { sections: [] })
    expect(useAppStore.getState().state).toBe('AWAITING_HUMAN')
    expect(useAppStore.getState().hitlType).toBe('outline_approval')
  })

  it('OSCILLATION_DETECTED sets oscillation flag', () => {
    useRunStore.getState().setOscillation(true, 'css_flip')
    expect(useRunStore.getState().activeRun?.oscillationDetected).toBe(true)
    expect(useRunStore.getState().activeRun?.oscillationType).toBe('css_flip')
  })

  it('HARD_STOP sets hard stop flag', () => {
    useRunStore.getState().setHardStop(true)
    expect(useRunStore.getState().activeRun?.hardStopFired).toBe(true)
  })

  it('DRAFT_CHUNK appends to live draft', () => {
    useRunStore.getState().appendDraftChunk('chunk1 ')
    useRunStore.getState().appendDraftChunk('chunk2')
    expect(useRunStore.getState().activeRun?.liveDraft).toBe('chunk1 chunk2')
  })

  it('PIPELINE_DONE sets status to completed and app to REVIEWING', () => {
    useRunStore.getState().setRunStatus('completed')
    useAppStore.getState().setState('REVIEWING')
    expect(useRunStore.getState().activeRun?.status).toBe('completed')
    expect(useAppStore.getState().state).toBe('REVIEWING')
  })

  it('PIPELINE_FAILED sets status to failed', () => {
    useRunStore.getState().setRunStatus('failed')
    expect(useRunStore.getState().activeRun?.status).toBe('failed')
  })
})
