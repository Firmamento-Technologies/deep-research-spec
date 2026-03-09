import React, { useState } from 'react'
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  } from '@dnd-kit/core'
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
  arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'

export interface OutlineSection {
  id: string
  title: string
  scope: string
  targetWords: number
}

interface OutlineDragListProps {
  docId: string
}

export function OutlineDragList({ docId }: OutlineDragListProps) {
  const { activeRun } = useRunStore()
  const { setState } = useAppStore()

  const [sections, setSections] = useState<OutlineSection[]>(() => {
    const raw = (activeRun as any)?.hitlPayload?.sections ?? []
    return raw.length > 0
      ? raw
      : [
          { id: '1', title: 'Introduzione',  scope: 'Panoramica del topic', targetWords: 500 },
          { id: '2', title: 'Background',    scope: 'Contesto e letteratura', targetWords: 800 },
          { id: '3', title: 'Analisi',       scope: 'Analisi dettagliata', targetWords: 1200 },
          { id: '4', title: 'Conclusioni',   scope: 'Sintesi e implicazioni', targetWords: 400 },
        ]
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  const handleDragEnd = (event: any) => {
    const { active, over } = event
    if (over && active.id !== over.id) {
      const oldIdx = sections.findIndex(s => s.id === active.id)
      const newIdx = sections.findIndex(s => s.id === over.id)
      setSections(arrayMove(sections, oldIdx, newIdx))
    }
  }

  const updateSection = (id: string, field: keyof OutlineSection, value: string | number) => {
    setSections(prev => prev.map(s => s.id === id ? { ...s, [field]: value } : s))
  }

  const addSection = () => {
    setSections(prev => [
      ...prev,
      { id: Date.now().toString(), title: 'Nuova sezione', scope: '', targetWords: 500 },
    ])
  }

  const removeSection = (id: string) => {
    setSections(prev => prev.filter(s => s.id !== id))
  }

  const handleApprove = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const res = await fetch(`/api/runs/${docId}/approve-outline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sections }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setState('PROCESSING')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleRegenerate = async () => {
    setSubmitting(true)
    setError(null)
    try {
      await fetch(`/api/runs/${docId}/approve-outline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sections, action: 'regenerate' }),
      })
      setState('PROCESSING')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={sections.map(s => s.id)} strategy={verticalListSortingStrategy}>
            {sections.map((section, idx) => (
              <SortableRow
                key={section.id}
                section={section}
                idx={idx}
                onUpdate={updateSection}
                onRemove={removeSection}
              />
            ))}
          </SortableContext>
        </DndContext>

        <button
          onClick={addSection}
          style={{
            marginTop: 8,
            background: 'transparent',
            border: '1px dashed #2A2D3A',
            borderRadius: 6,
            color: '#8B8FA8',
            fontSize: 12,
            fontFamily: 'monospace',
            padding: '8px 16px',
            cursor: 'pointer',
            width: '100%',
          }}
        >
          + Aggiungi Sezione
        </button>
      </div>

      {/* Footer */}
      <div
        style={{
          padding: '12px 20px',
          borderTop: '1px solid #2A2D3A',
          display: 'flex',
          gap: 10,
          alignItems: 'center',
          flexShrink: 0,
        }}
      >
        {error && (
          <span style={{ fontSize: 11, color: '#EF4444', fontFamily: 'monospace', flex: 1 }}>{error}</span>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <ActionBtn onClick={handleRegenerate} disabled={submitting} variant="ghost">
            Rigenera
          </ActionBtn>
          <ActionBtn onClick={handleApprove} disabled={submitting} variant="primary">
            {submitting ? 'Invio…' : 'Approva Outline'}
          </ActionBtn>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
function SortableRow({
  section,
  idx,
  onUpdate,
  onRemove,
}: {
  section: OutlineSection
  idx: number
  onUpdate: (id: string, field: keyof OutlineSection, value: string | number) => void
  onRemove: (id: string) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: section.id,
  })

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 10px',
        marginBottom: 6,
        background: isDragging ? '#1A1D27' : '#111318',
        border: `1px solid ${isDragging ? '#7C8CFF60' : '#2A2D3A'}`,
        borderRadius: 6,
        opacity: isDragging ? 0.85 : 1,
        boxShadow: isDragging ? '0 4px 16px rgba(0,0,0,0.4)' : 'none',
      }}
    >
      {/* Drag handle */}
      <span
        {...attributes}
        {...listeners}
        style={{ cursor: 'grab', color: '#50536A', fontSize: 14, flexShrink: 0, lineHeight: 1 }}
      >
        ☰
      </span>

      {/* Index */}
      <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#50536A', flexShrink: 0, width: 20 }}>
        §{idx + 1}
      </span>

      {/* Title */}
      <input
        value={section.title}
        onChange={e => onUpdate(section.id, 'title', e.target.value)}
        style={{
          flex: 2,
          background: 'transparent',
          border: 'none',
          borderBottom: '1px solid #2A2D3A',
          color: '#F0F1F6',
          fontSize: 12,
          fontFamily: 'monospace',
          padding: '2px 4px',
          outline: 'none',
        }}
        placeholder="Titolo sezione"
      />

      {/* Scope */}
      <input
        value={section.scope}
        onChange={e => onUpdate(section.id, 'scope', e.target.value)}
        style={{
          flex: 3,
          background: 'transparent',
          border: 'none',
          borderBottom: '1px solid #2A2D3A',
          color: '#8B8FA8',
          fontSize: 11,
          fontFamily: 'monospace',
          padding: '2px 4px',
          outline: 'none',
        }}
        placeholder="Scope"
      />

      {/* Target words */}
      <input
        type="number"
        value={section.targetWords}
        min={100}
        max={10000}
        step={100}
        onChange={e => onUpdate(section.id, 'targetWords', parseInt(e.target.value) || 500)}
        style={{
          width: 72,
          background: 'transparent',
          border: '1px solid #2A2D3A',
          borderRadius: 4,
          color: '#8B8FA8',
          fontSize: 11,
          fontFamily: 'monospace',
          padding: '2px 6px',
          outline: 'none',
          textAlign: 'right',
          flexShrink: 0,
        }}
      />
      <span style={{ fontSize: 9, color: '#50536A', flexShrink: 0 }}>w</span>

      {/* Delete */}
      <button
        onClick={() => onRemove(section.id)}
        style={{
          background: 'transparent',
          border: 'none',
          color: '#50536A',
          cursor: 'pointer',
          fontSize: 14,
          flexShrink: 0,
          lineHeight: 1,
        }}
        title="Rimuovi sezione"
      >
        ×
      </button>
    </div>
  )
}

function ActionBtn({
  children,
  onClick,
  disabled,
  variant,
}: {
  children: React.ReactNode
  onClick: () => void
  disabled?: boolean
  variant: 'primary' | 'ghost'
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '8px 18px',
        borderRadius: 6,
        fontSize: 12,
        fontFamily: 'monospace',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        border: variant === 'primary' ? 'none' : '1px solid #2A2D3A',
        background: variant === 'primary' ? '#7C8CFF' : 'transparent',
        color: variant === 'primary' ? '#0A0B0F' : '#8B8FA8',
        fontWeight: variant === 'primary' ? 700 : 400,
      }}
    >
      {children}
    </button>
  )
}
