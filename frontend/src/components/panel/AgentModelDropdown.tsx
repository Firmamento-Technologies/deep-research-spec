import { useState, useRef, useEffect } from 'react'
import { MODELS_BY_PROVIDER } from '../../constants/models'
import { useAppStore } from '../../store/useAppStore'
import { api } from '../../lib/api'

interface AgentModelDropdownProps {
  nodeId: string
  currentModel: string
}

export function AgentModelDropdown({ nodeId, currentModel }: AgentModelDropdownProps) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const { activeDocId } = useAppStore()

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  const handleSelect = async (modelId: string) => {
    if (!activeDocId || modelId === currentModel) { setOpen(false); return }
    setSaving(true)
    setOpen(false)
    try {
      await api.patch(`/api/runs/${activeDocId}/config`, { nodeId, newModel: modelId })
    } finally {
      setSaving(false)
    }
  }

  const shortName = currentModel?.split('/')[1] ?? currentModel ?? '—'

  return (
    <div ref={ref} className="relative inline-block">
      <button
        onClick={() => setOpen(o => !o)}
        className="bg-drs-s2 border border-drs-border rounded-input text-drs-muted text-[11px] font-mono px-[8px] py-[2px] cursor-pointer flex items-center gap-[4px] hover:border-drs-border-bright transition-colors"
        aria-label={`Cambia modello per ${nodeId}`}
        title={`Modello: ${currentModel}`}
      >
        {saving ? 'Salvataggio…' : shortName}
        <span className="text-[9px]">▾</span>
      </button>

      {open && (
        <div className="absolute top-full left-0 z-50 bg-drs-s1 border border-drs-border rounded-[6px] min-w-[220px] max-h-[320px] overflow-y-auto shadow-[0_8px_24px_rgba(0,0,0,0.6)]">
          {Object.entries(MODELS_BY_PROVIDER).map(([provider, models]) => (
            <div key={provider}>
              <div className="text-[9px] font-mono text-drs-faint p-[6px_10px_2px] tracking-[1px] uppercase">
                {provider}
              </div>
              {models.map(m => (
                <button
                  key={m.id}
                  onClick={() => handleSelect(m.id)}
                  className={`block w-full text-left p-[5px_10px] border-none text-[11px] font-mono cursor-pointer ${
                    m.id === currentModel
                      ? 'bg-drs-s2 text-drs-accent'
                      : 'bg-transparent text-drs-text'
                  }`}
                >
                  {m.name}
                  <span className="text-drs-faint ml-[6px] text-[9px]">
                    ${m.costIn}/{m.costOut}
                  </span>
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
