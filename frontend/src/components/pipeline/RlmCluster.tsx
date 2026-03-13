// RlmCluster — optional RLM recursive language model overlay (new coordinates)

interface RlmClusterProps {
  active: boolean
}

const RLM_COLOR = '#818CF8'

const NODES = [
  { id: 'rlm_adapter', label: 'RLM ADAPT.', x: 1280, y: 1160 },
  { id: 'deep_research_lm', label: 'DEEP RES. LM', x: 1280, y: 1230 },
  { id: 'section_budget_guard', label: 'SEC. BUDGET', x: 1280, y: 1300 },
]

export function RlmCluster({ active }: RlmClusterProps) {
  const opacity = active ? 1 : 0.25

  return (
    <>
      <div
        className="absolute text-[10px] font-mono font-semibold tracking-wider"
        style={{ left: 1280, top: 1135, opacity, color: `${RLM_COLOR}AA` }}
      >
        RLM
      </div>

      {NODES.map(node => (
        <div
          key={node.id}
          className="absolute w-[140px] h-[52px] rounded-lg flex items-center justify-center transition-all duration-300"
          style={{
            left: node.x,
            top: node.y,
            background: `${RLM_COLOR}0C`,
            border: `1.5px dashed ${RLM_COLOR}${active ? '80' : '30'}`,
            opacity,
            boxShadow: active ? `0 0 10px ${RLM_COLOR}30` : 'none',
          }}
        >
          <span className="text-[10px] font-mono text-drs-text">{node.label}</span>
        </div>
      ))}
    </>
  )
}
