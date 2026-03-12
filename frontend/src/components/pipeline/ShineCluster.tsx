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
        className="absolute text-[9px] font-mono text-drs-node-shine tracking-[1px]"
        style={{ left: 1690, top: 760, opacity }}
      >
        SHINE
      </div>

      {nodes.map(node => (
        <div
          key={node.id}
          className="absolute w-[160px] h-[56px] rounded-card flex items-center justify-center transition-[opacity,border-color] duration-400"
          style={{
            left: node.x,
            top: node.y,
            background: `${SHINE_COLOR}10`,
            border: `1px dashed ${SHINE_COLOR}${active ? 'AA' : '44'}`,
            opacity,
            boxShadow: active ? `0 0 12px ${SHINE_COLOR}40` : 'none',
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
