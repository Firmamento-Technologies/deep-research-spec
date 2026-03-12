import { useState, useRef, useEffect } from 'react'

interface ChapterExportMenuProps {
  docId: string
  sectionIdx?: number   // undefined = export full document
  label?: string
}

const FORMATS = [
  { id: 'docx', label: '⬇ DOCX' },
  { id: 'pdf', label: '⬇ PDF' },
  { id: 'markdown', label: '⬇ Markdown' },
  { id: 'json', label: '⬇ JSON' },
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
    <div ref={ref} className="relative inline-block">
      <button
        onClick={() => setOpen(o => !o)}
        className="bg-drs-s2 border border-drs-border rounded-input text-drs-muted text-[11px] font-mono p-[4px_10px] cursor-pointer flex items-center gap-[4px]"
      >
        ⬇ {label} <span className="text-[9px]">▾</span>
      </button>

      {open && (
        <div className="absolute bottom-full left-0 mb-[4px] bg-drs-s1 border border-drs-border rounded-[6px] overflow-hidden shadow-[0_4px_16px_rgba(0,0,0,0.5)] z-30 min-w-[140px]">
          {FORMATS.map(f => (
            <button
              key={f.id}
              onClick={() => handleDownload(f.id)}
              className="block w-full text-left p-[7px_12px] bg-transparent border-none text-drs-text text-[12px] font-mono cursor-pointer hover:bg-drs-s2"
            >
              {f.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
