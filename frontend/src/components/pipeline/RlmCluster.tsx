// RlmCluster — optional RLM recursive language model overlay

interface RlmClusterProps {
  active: boolean
}

const RLM_COLOR = '#818CF8'

export function RlmCluster({ active }: RlmClusterProps) {
  const opacity = active ? 1 : 0.3

  const nodes = [
    { id: 'rlm_adapter', label: 'RLM ADAPTER', x: 1700, y: 1400 },
    { id: 'deep_research_lm', label: 'DEEP RESEARCH LM', x: 1700, y: 1480 },
    { id: 'section_budget_guard', label: 'SECTION BUDGET', x: 1700, y: 1560 },
  ]

  return (
    <>
      {/* Cluster label */}
      <div
        className="absolute text-[9px] font-mono text-drs-node-rlm tracking-[1px]"
        style={{ left: 1700, top: 1360, opacity }}
      >
        RLM
      </div>

      {nodes.map(node => (
        <div
          key={node.id}
          className="absolute w-[160px] h-[56px] rounded-card flex items-center justify-center transition-[opacity,border-color] duration-400"
          style={{
            left: node.x,
            top: node.y,
            background: `${RLM_COLOR}10`,
            border: `1px dashed ${RLM_COLOR}${active ? 'AA' : '44'}`,
            opacity,
            boxShadow: active ? `0 0 12px ${RLM_COLOR}40` : 'none',
          }}
        >
          <span className="text-[10px] font-mono text-drs-text">
            {node.label}
          </span>
        </div>
      ))}
    </>
  )
}
