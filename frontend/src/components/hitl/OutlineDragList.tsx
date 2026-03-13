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
import { api } from '../../lib/api'

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
  const { setState, hitlPayload, closeHitl } = useAppStore()

  const [sections, setSections] = useState<OutlineSection[]>(() => {
    const raw = ((hitlPayload as Record<string, unknown> | null)?.sections as OutlineSection[] | undefined) ?? []
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

  const handleDragEnd = (event: { active: { id: string | number }; over: { id: string | number } | null }) => {
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
      await api.post(`/api/runs/${docId}/approve-outline`, { sections })
      closeHitl()
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
      await api.post(`/api/runs/${docId}/approve-outline`, { sections, action: 'regenerate' })
      closeHitl()
      setState('PROCESSING')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* List */}
      <div className="flex-1 overflow-y-auto p-[16px_20px]">
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
          className="mt-[8px] bg-transparent border border-dashed border-drs-border rounded-[6px] text-drs-muted text-[12px] font-mono p-[8px_16px] cursor-pointer w-full"
        >
          + Aggiungi Sezione
        </button>
      </div>

      {/* Footer */}
      <div className="p-[12px_20px] border-t border-drs-border flex gap-[10px] items-center shrink-0">
        {error && (
          <span className="text-[11px] text-drs-red font-mono flex-1">{error}</span>
        )}
        <div className="ml-auto flex gap-[8px]">
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
      className="flex items-center gap-[8px] p-[8px_10px] mb-[6px] rounded-[6px]"
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        background: isDragging ? '#1A1D27' : '#111318',
        border: `1px solid ${isDragging ? '#7C8CFF60' : '#2A2D3A'}`,
        opacity: isDragging ? 0.85 : 1,
        boxShadow: isDragging ? '0 4px 16px rgba(0,0,0,0.4)' : 'none',
      }}
    >
      {/* Drag handle */}
      <span
        {...attributes}
        {...listeners}
        className="cursor-grab text-drs-faint text-[14px] shrink-0 leading-none"
      >
        ☰
      </span>

      {/* Index */}
      <span className="text-[11px] font-mono text-drs-faint shrink-0 w-[20px]">
        §{idx + 1}
      </span>

      {/* Title */}
      <input
        value={section.title}
        onChange={e => onUpdate(section.id, 'title', e.target.value)}
        className="flex-[2] bg-transparent border-0 border-b border-drs-border text-drs-text text-[12px] font-mono p-[2px_4px] outline-none"
        placeholder="Titolo sezione"
      />

      {/* Scope */}
      <input
        value={section.scope}
        onChange={e => onUpdate(section.id, 'scope', e.target.value)}
        className="flex-[3] bg-transparent border-0 border-b border-drs-border text-drs-muted text-[11px] font-mono p-[2px_4px] outline-none"
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
        className="w-[72px] bg-transparent border border-drs-border rounded-input text-drs-muted text-[11px] font-mono p-[2px_6px] outline-none text-right shrink-0"
      />
      <span className="text-[9px] text-drs-faint shrink-0">w</span>

      {/* Delete */}
      <button
        onClick={() => onRemove(section.id)}
        className="bg-transparent border-none text-drs-faint cursor-pointer text-[14px] shrink-0 leading-none"
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
      className={`p-[8px_18px] rounded-[6px] text-[12px] font-mono ${
        disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer opacity-100'
      } ${
        variant === 'primary'
          ? 'border-none bg-drs-accent text-drs-bg font-bold'
          : 'border border-drs-border bg-transparent text-drs-muted font-normal'
      }`}
    >
      {children}
    </button>
  )
}
