import { useAppStore } from '../useAppStore'

const getState = () => useAppStore.getState()
const { setState } = useAppStore

beforeEach(() => {
  setState({
    state: 'IDLE',
    activeDocId: null,
    sidebarCollapsed: false,
    rightPanelCollapsed: false,
    selectedNodeId: null,
    hitlType: null,
    hitlPayload: null,
  })
})

describe('useAppStore', () => {
  it('starts in IDLE state', () => {
    expect(getState().state).toBe('IDLE')
  })

  it('setState transitions app state', () => {
    getState().setState('PROCESSING')
    expect(getState().state).toBe('PROCESSING')
  })

  it('setActiveDocId sets and clears document id', () => {
    getState().setActiveDocId('doc-123')
    expect(getState().activeDocId).toBe('doc-123')

    getState().setActiveDocId(null)
    expect(getState().activeDocId).toBeNull()
  })

  it('setSelectedNode updates selectedNodeId', () => {
    getState().setSelectedNode('writer')
    expect(getState().selectedNodeId).toBe('writer')
  })

  it('toggleSidebar flips sidebarCollapsed', () => {
    expect(getState().sidebarCollapsed).toBe(false)
    getState().toggleSidebar()
    expect(getState().sidebarCollapsed).toBe(true)
    getState().toggleSidebar()
    expect(getState().sidebarCollapsed).toBe(false)
  })

  it('toggleRightPanel flips rightPanelCollapsed', () => {
    expect(getState().rightPanelCollapsed).toBe(false)
    getState().toggleRightPanel()
    expect(getState().rightPanelCollapsed).toBe(true)
  })

  it('openHitl sets type and payload', () => {
    getState().openHitl('outline_approval', { sections: ['A', 'B'] })
    expect(getState().hitlType).toBe('outline_approval')
    expect(getState().hitlPayload).toEqual({ sections: ['A', 'B'] })
  })

  it('closeHitl clears type and payload', () => {
    getState().openHitl('escalation', { reason: 'low_css' })
    getState().closeHitl()
    expect(getState().hitlType).toBeNull()
    expect(getState().hitlPayload).toBeNull()
  })

  it('follows valid state transitions', () => {
    getState().setState('CONVERSING')
    getState().setState('PROCESSING')
    getState().setState('AWAITING_HUMAN')
    getState().setState('PROCESSING')
    getState().setState('REVIEWING')
    getState().setState('CONVERSING')
    expect(getState().state).toBe('CONVERSING')
  })
})
