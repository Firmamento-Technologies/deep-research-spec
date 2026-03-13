import React, { useState } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'

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
  if (status === 'failed')    return <span title="Fallita" className="text-drs-red">❌</span>
  if (status === 'waiting')   return <span title="In attesa" className="text-drs-faint text-[14px]">⏳</span>
  // running — animated green dot
  return (
    <span
      title="In esecuzione"
      className="inline-block w-[8px] h-[8px] rounded-full bg-drs-green align-middle shadow-[0_0_6px_#22C55E]"
      style={{ animation: 'dot-pulse 1s ease-in-out infinite' }}
    />
  )
}

export function SectionItem({ idx, title, status, docId, collapsed }: SectionItemProps) {
  const [hovered, setHovered] = useState(false)
  const { setState, setActiveDocId, setSelectedNode } = useAppStore()
  const { activeRun } = useRunStore()

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
    if (activeRun) {
      setSelectedNode(`writer_single`)
      setState('PROCESSING')
    }
  }

  if (collapsed) {
    return (
      <div
        title={`§${idx + 1} ${title}`}
        onClick={handleClick}
        className="w-[8px] h-[8px] rounded-full mx-auto my-[6px]"
        style={{
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
      className="flex items-center gap-[8px] p-[4px_8px] rounded-input relative transition-colors duration-150"
      style={{
        cursor: status === 'completed' ? 'pointer' : 'default',
        background: hovered ? '#1A1D2740' : 'transparent',
      }}
    >
      <div className="shrink-0 w-[16px] flex items-center justify-center">
        <StatusIcon status={status} />
      </div>

      <span
        className={`flex-1 text-[12px] overflow-hidden text-ellipsis whitespace-nowrap ${
          status === 'completed' ? 'text-drs-text' : 'text-drs-muted'
        }`}
      >
        §{idx + 1} {title}
      </span>

      {/* Hover micro-menu */}
      {hovered && (
        <div className="flex gap-[4px] shrink-0">
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
      aria-label={title}
      onClick={onClick}
      className="bg-drs-s2 border border-drs-border rounded-[3px] text-drs-muted text-[9px] font-mono p-[2px_5px] cursor-pointer leading-none"
    >
      {children}
    </button>
  )
}
