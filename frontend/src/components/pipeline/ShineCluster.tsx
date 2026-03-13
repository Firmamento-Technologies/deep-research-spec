// ShineCluster — optional SHINE LoRA serving overlay (new coordinates)

interface ShineClusterProps {
  active: boolean
}

const SHINE_COLOR = '#14B8A6'

const NODES = [
  { id: 'shine_singleton', label: 'SHINE', x: 1280, y: 610 },
  { id: 'shine_hypernetwork', label: 'HYPERNET', x: 1280, y: 680 },
  { id: 'shine_lora', label: 'LORA', x: 1280, y: 750 },
]

export function ShineCluster({ active }: ShineClusterProps) {
  const opacity = active ? 1 : 0.25

  return (
    <>
      <div
        className="absolute text-[10px] font-mono font-semibold tracking-wider"
        style={{ left: 1280, top: 585, opacity, color: `${SHINE_COLOR}AA` }}
      >
        SHINE
      </div>

      {NODES.map(node => (
        <div
          key={node.id}
          className="absolute w-[140px] h-[52px] rounded-lg flex items-center justify-center transition-all duration-300"
          style={{
            left: node.x,
            top: node.y,
            background: `${SHINE_COLOR}0C`,
            border: `1.5px dashed ${SHINE_COLOR}${active ? '80' : '30'}`,
            opacity,
            boxShadow: active ? `0 0 10px ${SHINE_COLOR}30` : 'none',
          }}
        >
          <span className="text-[10px] font-mono text-drs-text">{node.label}</span>
        </div>
      ))}
    </>
  )
}
