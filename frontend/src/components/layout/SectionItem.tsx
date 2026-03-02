import React, { useState } from 'react'
import { useAppStore } from '../../store/useAppStore'

export type SectionStatus = 'waiting' | 'running' | 'completed' | 'failed'

interface SectionItemProps {
  idx: number
  title: string
  status: SectionStatus
  docId: string
  collapsed: boolean  // sidebar collapsed to 48px
}

function StatusIcon({ status }: { status: SectionStatus }) {
  if (status === 'completed') return <span title="Completata">✅</span>
  if (status === 'failed')    return <span title="Fallita" style={{ color: '#EF4444' }}>❌</span>
  if (status === 'waiting')   return <span title="In attesa" style={{ color: '#50536A', fontSize: 14 }}>⏳</span>
  // running — animated green dot
  return (
    <span
      title="In esecuzione"
      style={{
        display: 'inline-block',
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: '#22C55E',
        boxShadow: '0 0 6px #22C55E',
        animation: 'pulse-dot 1s ease-in-out infinite',
        verticalAlign: 'middle',
      }}
    />
  )
}

export function SectionItem({ idx, title, status, docId, collapsed }: SectionItemProps) {
  const [hovered, setHovered] = useState(false)
  const { setState, setActiveDocId } = useAppStore()

  const handleClick = () => {
    if (status === 'completed') {
      setActiveDocId(docId)
      setState('REVIEWING')
    }
  }

  const handleExport = async (e: React.MouseEvent, format: 'docx') => {
    e.stopPropagation()
    window.open(`/api/runs/${docId}/output/${format}`, '_blank')
  }

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation()
    // copy section title as placeholder — real impl copies markdown content
    await navigator.clipboard.writeText(`§${idx + 1} ${title}`)
  }

  const handleLog = (e: React.MouseEvent) => {
    e.stopPropagation()
    // navigate to log — sets selected node context
  }

  if (collapsed) {
    return (
      <div
        title={`§${idx + 1} ${title}`}
        onClick={handleClick}
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          margin: '6px auto',
          background:
            status === 'completed' ? '#4F6EF7' :
            status === 'running'   ? '#22C55E' :
            status === 'failed'    ? '#EF4444' :
            '#50536A',
          cursor: status === 'completed' ? 'pointer' : 'default',
        }}
      />
    )
  }

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={handleClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '4px 8px',
        borderRadius: 4,
        cursor: status === 'completed' ? 'pointer' : 'default',
        background: hovered ? '#1A1D2740' : 'transparent',
        position: 'relative',
        transition: 'background 0.15s',
      }}
    >
      <div style={{ flexShrink: 0, width: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <StatusIcon status={status} />
      </div>

      <span
        style={{
          flex: 1,
          fontSize: 12,
          color: status === 'completed' ? '#F0F1F6' : '#8B8FA8',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        §{idx + 1} {title}
      </span>

      {/* Hover micro-menu */}
      {hovered && (
        <div
          style={{
            display: 'flex',
            gap: 4,
            flexShrink: 0,
          }}
        >
          <MicroBtn title="Esporta DOCX" onClick={e => handleExport(e, 'docx')}>⬇ DOCX</MicroBtn>
          <MicroBtn title="Copia" onClick={handleCopy}>Copia</MicroBtn>
          <MicroBtn title="Log agenti" onClick={handleLog}>Log</MicroBtn>
        </div>
      )}
    </div>
  )
}

function MicroBtn({
  children,
  title,
  onClick,
}: {
  children: React.ReactNode
  title: string
  onClick: (e: React.MouseEvent) => void
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      style={{
        background: '#1A1D27',
        border: '1px solid #2A2D3A',
        borderRadius: 3,
        color: '#8B8FA8',
        fontSize: 9,
        fontFamily: 'monospace',
        padding: '2px 5px',
        cursor: 'pointer',
        lineHeight: 1,
      }}
    >
      {children}
    </button>
  )
}
