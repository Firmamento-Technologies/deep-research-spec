import React, { useState, useRef, useEffect } from 'react'

interface ChapterExportMenuProps {
  docId: string
  sectionIdx?: number   // undefined = export full document
  label?: string
}

const FORMATS = [
  { id: 'docx',     label: '⬇ DOCX' },
  { id: 'pdf',      label: '⬇ PDF' },
  { id: 'markdown', label: '⬇ Markdown' },
  { id: 'json',     label: '⬇ JSON' },
] as const

export function ChapterExportMenu({ docId, sectionIdx, label = 'Esporta' }: ChapterExportMenuProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [])

  const handleDownload = (format: string) => {
    const base = `/api/runs/${docId}/output/${format}`
    const url = sectionIdx != null ? `${base}?section=${sectionIdx}` : base
    window.open(url, '_blank')
    setOpen(false)
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          background: '#1A1D27',
          border: '1px solid #2A2D3A',
          borderRadius: 4,
          color: '#8B8FA8',
          fontSize: 11,
          fontFamily: 'monospace',
          padding: '4px 10px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 4,
        }}
      >
        ⬇ {label} <span style={{ fontSize: 9 }}>▾</span>
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            marginBottom: 4,
            background: '#111318',
            border: '1px solid #2A2D3A',
            borderRadius: 6,
            overflow: 'hidden',
            boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
            zIndex: 30,
            minWidth: 140,
          }}
        >
          {FORMATS.map(f => (
            <button
              key={f.id}
              onClick={() => handleDownload(f.id)}
              style={{
                display: 'block',
                width: '100%',
                textAlign: 'left',
                padding: '7px 12px',
                background: 'transparent',
                border: 'none',
                color: '#F0F1F6',
                fontSize: 12,
                fontFamily: 'monospace',
                cursor: 'pointer',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = '#1A1D27')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              {f.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
