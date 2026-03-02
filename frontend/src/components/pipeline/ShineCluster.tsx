// ShineCluster — optional SHINE LoRA serving overlay

interface ShineClusterProps {
  active: boolean
}

const SHINE_COLOR = '#14B8A6'

export function ShineCluster({ active }: ShineClusterProps) {
  const opacity = active ? 1 : 0.3

  const nodes = [
    { id: 'shine_singleton', label: 'SHINE SINGLETON', x: 1700, y: 800 },
    { id: 'shine_hypernetwork', label: 'SHINE HYPERNET', x: 1700, y: 880 },
    { id: 'shine_lora', label: 'LORA WEIGHTS', x: 1700, y: 960 },
  ]

  return (
    <>
      {/* Cluster label */}
      <div
        style={{
          position: 'absolute',
          left: 1690,
          top: 760,
          fontSize: 9,
          fontFamily: 'monospace',
          color: SHINE_COLOR,
          opacity,
          letterSpacing: 1,
        }}
      >
        SHINE
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
            background: `${SHINE_COLOR}10`,
            border: `1px dashed ${SHINE_COLOR}${active ? 'AA' : '44'}`,
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity,
            transition: 'opacity 0.4s, border-color 0.4s',
            boxShadow: active ? `0 0 12px ${SHINE_COLOR}40` : 'none',
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
