import React from 'react'

interface RlmClusterProps {
  active: boolean
}

const RLM_COLOR = '#818CF8'

export function RlmCluster({ active }: RlmClusterProps) {
  const opacity = active ? 1 : 0.3

  const nodes = [
    { id: 'rlm_adapter',         label: 'RLM ADAPTER',       x: 1700, y: 1400 },
    { id: 'deep_research_lm',    label: 'DEEP RESEARCH LM',  x: 1700, y: 1480 },
    { id: 'section_budget_guard',label: 'SECTION BUDGET',    x: 1700, y: 1560 },
  ]

  return (
    <>
      {/* Cluster label */}
      <div
        style={{
          position: 'absolute',
          left: 1700,
          top: 1360,
          fontSize: 9,
          fontFamily: 'monospace',
          color: RLM_COLOR,
          opacity,
          letterSpacing: 1,
        }}
      >
        RLM
      </div>

      {nodes.map(node => (
        <div
          key={node.id}
          style={{
            position: 'absolute',
            left: node.x,
            top: node.y,
            width: 160,
            height: 56,
            background: `${RLM_COLOR}10`,
            border: `1px dashed ${RLM_COLOR}${ active ? 'AA' : '44' }`,
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity,
            transition: 'opacity 0.4s, border-color 0.4s',
            boxShadow: active ? `0 0 12px ${RLM_COLOR}40` : 'none',
          }}
        >
          <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#F0F1F6' }}>
            {node.label}
          </span>
        </div>
      ))}
    </>
  )
}
