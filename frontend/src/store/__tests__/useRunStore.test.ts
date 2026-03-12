import { useRunStore } from '../useRunStore'
import type { RunState } from '../../types/run'

const getState = () => useRunStore.getState()
const { setState } = useRunStore

function makeRun(overrides: Partial<RunState> = {}): RunState {
  return {
    docId: 'test-doc',
    topic: 'Test Topic',
    status: 'running',
    qualityPreset: 'Balanced',
    targetWords: 8000,
    maxBudget: 50,
    budgetSpent: 0,
    budgetRemainingPct: 100,
    totalSections: 8,
    currentSection: 0,
    currentIteration: 0,
    nodes: {},
    cssScores: { content: 0, style: 0, source: 0 },
    juryVerdicts: [],
    sections: [
      { idx: 0, title: 'Intro', content: '', wordCount: 0, approved: false, iterations: 0, cssScores: { content: 0, style: 0, source: 0 } },
      { idx: 1, title: 'Body', content: '', wordCount: 0, approved: false, iterations: 0, cssScores: { content: 0, style: 0, source: 0 } },
    ],
    shineActive: false,
    rlmMode: false,
    hardStopFired: false,
    oscillationDetected: false,
    forceApprove: false,
    ...overrides,
  }
}

beforeEach(() => {
  setState({ activeRun: null, completedRuns: [] })
})

describe('useRunStore', () => {
  it('starts with no active run', () => {
    expect(getState().activeRun).toBeNull()
    expect(getState().completedRuns).toEqual([])
  })

  it('setActiveRun sets the active run', () => {
    const run = makeRun()
    getState().setActiveRun(run)
    expect(getState().activeRun?.docId).toBe('test-doc')
  })

  it('updateNode creates new node entry', () => {
    getState().setActiveRun(makeRun())
    getState().updateNode('writer', { status: 'running', startedAt: new Date() })
    expect(getState().activeRun?.nodes['writer']?.status).toBe('running')
  })

  it('updateNode merges with existing node', () => {
    getState().setActiveRun(makeRun())
    getState().updateNode('writer', { status: 'running' })
    getState().updateNode('writer', { status: 'completed', durationMs: 1500 })
    const node = getState().activeRun?.nodes['writer']
    expect(node?.status).toBe('completed')
    expect(node?.durationMs).toBe(1500)
  })

  it('updateNode is a no-op when no active run', () => {
    getState().updateNode('writer', { status: 'running' })
    expect(getState().activeRun).toBeNull()
  })

  it('updateBudget updates spent and remaining', () => {
    getState().setActiveRun(makeRun())
    getState().updateBudget(12.5, 75)
    expect(getState().activeRun?.budgetSpent).toBe(12.5)
    expect(getState().activeRun?.budgetRemainingPct).toBe(75)
  })

  it('updateCSS updates css scores', () => {
    getState().setActiveRun(makeRun())
    getState().updateCSS({ content: 0.85, style: 0.72, source: 0.91 })
    expect(getState().activeRun?.cssScores.content).toBe(0.85)
  })

  it('approveSection marks specific section approved', () => {
    getState().setActiveRun(makeRun())
    getState().approveSection(0)
    expect(getState().activeRun?.sections[0].approved).toBe(true)
    expect(getState().activeRun?.sections[1].approved).toBe(false)
  })

  it('setOscillation updates oscillation state', () => {
    getState().setActiveRun(makeRun())
    getState().setOscillation(true, 'css_flip')
    expect(getState().activeRun?.oscillationDetected).toBe(true)
    expect(getState().activeRun?.oscillationType).toBe('css_flip')
  })

  it('setRunStatus changes run status', () => {
    getState().setActiveRun(makeRun())
    getState().setRunStatus('completed')
    expect(getState().activeRun?.status).toBe('completed')
  })

  it('setHardStop sets hard stop flag', () => {
    getState().setActiveRun(makeRun())
    getState().setHardStop(true)
    expect(getState().activeRun?.hardStopFired).toBe(true)
  })

  it('appendDraftChunk builds up live draft', () => {
    getState().setActiveRun(makeRun())
    getState().appendDraftChunk('Hello ')
    getState().appendDraftChunk('world')
    expect(getState().activeRun?.liveDraft).toBe('Hello world')
  })

  it('clearDraft resets live draft', () => {
    getState().setActiveRun(makeRun())
    getState().appendDraftChunk('some text')
    getState().clearDraft()
    expect(getState().activeRun?.liveDraft).toBe('')
  })

  it('archiveRun moves active run to completedRuns', () => {
    const run = makeRun()
    getState().setActiveRun(run)
    getState().archiveRun()
    expect(getState().activeRun).toBeNull()
    expect(getState().completedRuns).toHaveLength(1)
    expect(getState().completedRuns[0].docId).toBe('test-doc')
  })

  it('archiveRun is a no-op when no active run', () => {
    getState().archiveRun()
    expect(getState().completedRuns).toEqual([])
  })
})
