import { useState } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { api } from '../../lib/api'
import { Source, SourceList } from '../panel/SourceList'
import { HitlActionBtn } from './HitlActionBtn'

interface Violation {
  start: number
  end: number
  reason: string
}

interface FeedbackItem {
  severity: 'HIGH' | 'MEDIUM' | 'LOW'
  category: string
  text: string
  fixSuggested?: string
}

interface SectionReviewSplitProps {
  docId: string
}

export function SectionReviewSplit({ docId }: SectionReviewSplitProps) {
  const { setState, hitlPayload, closeHitl } = useAppStore()

  const payload = (hitlPayload ?? {}) as Record<string, unknown>
  const draft: string = (payload.draft as string) ?? ''
  const violations: Violation[] = (payload.violations as Violation[]) ?? []
  const feedback: FeedbackItem[] = ((payload.feedbackItems as FeedbackItem[]) ?? []).sort(
    (a: FeedbackItem, b: FeedbackItem) => severityOrder(b.severity) - severityOrder(a.severity)
  )
  const sources: Source[] = (payload.sources as Source[]) ?? []

  const [manualEdit, setManualEdit] = useState(false)
  const [manualText, setManualText] = useState(draft)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const post = async (action: 'approve' | 'regenerate' | 'edit', editContent?: string) => {
    setSubmitting(true)
    setError(null)
    try {
      const body: Record<string, unknown> = {
        section_idx: payload.sectionIdx ?? 0,
        action,
      }
      if (editContent !== undefined) body.edit_content = editContent
      await api.post(`/api/runs/${docId}/approve-section`, body)
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
      <div className="flex-1 flex overflow-hidden">
        {/* LEFT — Draft */}
        <div className="flex-1 border-r border-drs-border overflow-y-auto p-[16px_20px]">
          <div className="text-[10px] font-mono text-drs-faint tracking-[1px] mb-[10px]">
            DRAFT
          </div>

          {manualEdit ? (
            <textarea
              value={manualText}
              onChange={e => setManualText(e.target.value)}
              className="w-full min-h-[400px] bg-drs-bg border border-drs-border rounded-[6px] text-drs-text text-[12px] font-mono p-[12px] resize-y outline-none leading-[1.7]"
            />
          ) : (
            <HighlightedDraft text={draft} violations={violations} />
          )}
        </div>

        {/* RIGHT — Feedback + Sources */}
        <div className="w-[340px] shrink-0 overflow-y-auto p-[16px] flex flex-col gap-[16px]">
          {/* Feedback */}
          <div>
            <div className="text-[10px] font-mono text-drs-faint tracking-[1px] mb-[8px]">
              FEEDBACK REFLECTOR
            </div>
            {feedback.length === 0 && (
              <div className="text-[11px] text-drs-faint font-mono">Nessun feedback.</div>
            )}
            {feedback.map((item, i) => (
              <FeedbackCard key={i} item={item} />
            ))}
          </div>

          {/* Sources */}
          {sources.length > 0 && <SourceList sources={sources} />}
        </div>
      </div>

      {/* Footer */}
      <div className="p-[12px_20px] border-t border-drs-border flex gap-[10px] items-center shrink-0">
        {error && (
          <span className="text-[11px] text-drs-red font-mono">{error}</span>
        )}
        <div className="ml-auto flex gap-[8px]">
          <HitlActionBtn variant="ghost" disabled={submitting}
            onClick={() => manualEdit ? post('edit', manualText) : setManualEdit(true)}>
            {manualEdit ? 'Invia Modifica' : 'Modifica Manuale'}
          </HitlActionBtn>
          {manualEdit && (
            <HitlActionBtn variant="ghost" disabled={submitting} onClick={() => setManualEdit(false)}>
              Annulla
            </HitlActionBtn>
          )}
          <HitlActionBtn variant="ghost" disabled={submitting} onClick={() => post('regenerate')}>
            Rigenera
          </HitlActionBtn>
          <HitlActionBtn variant="primary" disabled={submitting} onClick={() => post('approve')}>
            {submitting ? 'Invio…' : 'Approva'}
          </HitlActionBtn>
        </div>
      </div>
    </div>
  )
}

function FeedbackCard({ item }: { item: FeedbackItem }) {
  const [expanded, setExpanded] = useState(false)
  const color =
    item.severity === 'HIGH' ? '#EF4444' :
      item.severity === 'MEDIUM' ? '#F97316' : '#EAB308'

  return (
    <div
      className="bg-drs-s1 rounded-[6px] p-[8px_10px] mb-[6px]"
      style={{ border: `1px solid ${color}30` }}
    >
      <div className="flex gap-[6px] items-center mb-[3px]">
        <span
          className="text-[9px] font-mono rounded-[3px] p-[1px_5px]"
          style={{
            color,
            background: `${color}20`,
            border: `1px solid ${color}60`,
          }}
        >
          {item.severity}
        </span>
        <span className="text-[11px] font-mono text-drs-text">
          {item.category}
        </span>
      </div>
      <div className="text-[11px] text-drs-muted leading-[1.5]">{item.text}</div>
      {item.fixSuggested && (
        <button
          onClick={() => setExpanded(o => !o)}
          className="mt-[4px] bg-transparent border-none text-drs-accent text-[10px] cursor-pointer p-0"
        >
          {expanded ? '▾' : '▸'} Fix suggerito
        </button>
      )}
      {expanded && item.fixSuggested && (
        <div className="mt-[4px] text-[10px] text-drs-muted font-mono bg-drs-bg rounded-input p-[6px_8px] whitespace-pre-wrap break-words">
          {item.fixSuggested}
        </div>
      )}
    </div>
  )
}

function severityOrder(s: string) {
  return s === 'HIGH' ? 3 : s === 'MEDIUM' ? 2 : 1
}

function HighlightedDraft({ text, violations }: { text: string; violations: Violation[] }) {
  if (!violations.length) {
    return (
      <pre className="whitespace-pre-wrap break-words text-[13px] leading-[1.8] text-drs-text font-[inherit]">
        {text}
      </pre>
    )
  }

  const sorted = [...violations].sort((a, b) => a.start - b.start)
  const segments: Array<{ text: string; violation?: Violation }> = []
  let cursor = 0

  for (const v of sorted) {
    if (v.start > cursor) segments.push({ text: text.slice(cursor, v.start) })
    segments.push({ text: text.slice(v.start, v.end), violation: v })
    cursor = v.end
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor) })

  return (
    <pre className="whitespace-pre-wrap break-words text-[13px] leading-[1.8] text-drs-text font-[inherit]">
      {segments.map((seg, i) =>
        seg.violation ? (
          <mark
            key={i}
            title={seg.violation.reason}
            style={{ background: 'rgba(202,138,4,0.25)', borderRadius: '2px' }}
          >
            {seg.text}
          </mark>
        ) : (
          <span key={i}>{seg.text}</span>
        )
      )}
    </pre>
  )
}

