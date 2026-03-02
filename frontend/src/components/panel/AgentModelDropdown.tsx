import React, { useState, useRef, useEffect } from 'react'
import { MODELS_BY_PROVIDER } from '../../constants/models'
import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'

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
      await fetch(`/api/runs/${activeDocId}/config`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodeId, newModel: modelId }),
      })
    } finally {
      setSaving(false)
    }
  }

  const shortName = currentModel?.split('/')[1] ?? currentModel ?? '—'

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
          padding: '2px 8px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 4,
        }}
      >
        {saving ? 'Salvataggio…' : shortName}
        <span style={{ fontSize: 9 }}>▾</span>
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            zIndex: 50,
            background: '#111318',
            border: '1px solid #2A2D3A',
            borderRadius: 6,
            minWidth: 220,
            maxHeight: 320,
            overflowY: 'auto',
            boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
          }}
        >
          {Object.entries(MODELS_BY_PROVIDER).map(([provider, models]) => (
            <div key={provider}>
              <div
                style={{
                  fontSize: 9,
                  fontFamily: 'monospace',
                  color: '#50536A',
                  padding: '6px 10px 2px',
                  letterSpacing: 1,
                  textTransform: 'uppercase',
                }}
              >
                {provider}
              </div>
              {models.map(m => (
                <button
                  key={m.id}
                  onClick={() => handleSelect(m.id)}
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    padding: '5px 10px',
                    background: m.id === currentModel ? '#1A1D27' : 'transparent',
                    border: 'none',
                    color: m.id === currentModel ? '#7C8CFF' : '#F0F1F6',
                    fontSize: 11,
                    fontFamily: 'monospace',
                    cursor: 'pointer',
                  }}
                >
                  {m.name}
                  <span style={{ color: '#50536A', marginLeft: 6, fontSize: 9 }}>
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
