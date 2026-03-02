import type React from 'react'
import { useState } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'
import { Source, SourceList } from '../panel/SourceList'

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
  const { setState } = useAppStore()
  const { activeRun } = useRunStore()

  const payload = (activeRun as any)?.hitlPayload ?? {}
  const draft: string = payload.draft ?? ''
  const violations: Violation[] = payload.violations ?? []
  const feedback: FeedbackItem[] = (payload.feedbackItems ?? []).sort(
    (a: FeedbackItem, b: FeedbackItem) => severityOrder(b.severity) - severityOrder(a.severity)
  )
  const sources: Source[] = payload.sources ?? []

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
      const res = await fetch(`/api/runs/${docId}/approve-section`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setState('PROCESSING')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  // Highlight violations in markdown text
  const highlightedDraft = applyViolationHighlights(draft, violations)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* LEFT — Draft */}
        <div
          style={{
            flex: 1,
            borderRight: '1px solid #2A2D3A',
            overflowY: 'auto',
            padding: '16px 20px',
          }}
        >
          <div style={{ fontSize: 10, fontFamily: 'monospace', color: '#50536A', letterSpacing: 1, marginBottom: 10 }}>
            DRAFT
          </div>

          {manualEdit ? (
            <textarea
              value={manualText}
              onChange={e => setManualText(e.target.value)}
              style={{
                width: '100%',
                minHeight: 400,
                background: '#0A0B0F',
                border: '1px solid #2A2D3A',
                borderRadius: 6,
                color: '#F0F1F6',
                fontSize: 12,
                fontFamily: 'monospace',
                padding: 12,
                resize: 'vertical',
                outline: 'none',
                lineHeight: 1.7,
              }}
            />
          ) : (
            <div
              style={{ fontSize: 13, lineHeight: 1.8, color: '#F0F1F6' }}
              dangerouslySetInnerHTML={{ __html: highlightedDraft }}
            />
          )}
        </div>

        {/* RIGHT — Feedback + Sources */}
        <div
          style={{
            width: 340,
            flexShrink: 0,
            overflowY: 'auto',
            padding: '16px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
          }}
        >
          {/* Feedback */}
          <div>
            <div style={{ fontSize: 10, fontFamily: 'monospace', color: '#50536A', letterSpacing: 1, marginBottom: 8 }}>
              FEEDBACK REFLECTOR
            </div>
            {feedback.length === 0 && (
              <div style={{ fontSize: 11, color: '#50536A', fontFamily: 'monospace' }}>Nessun feedback.</div>
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
          <span style={{ fontSize: 11, color: '#EF4444', fontFamily: 'monospace' }}>{error}</span>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <ActionBtn variant="ghost" disabled={submitting}
            onClick={() => manualEdit ? post('edit', manualText) : setManualEdit(true)}>
            {manualEdit ? 'Invia Modifica' : 'Modifica Manuale'}
          </ActionBtn>
          {manualEdit && (
            <ActionBtn variant="ghost" disabled={submitting} onClick={() => setManualEdit(false)}>
              Annulla
            </ActionBtn>
          )}
          <ActionBtn variant="ghost" disabled={submitting} onClick={() => post('regenerate')}>
            Rigenera
          </ActionBtn>
          <ActionBtn variant="primary" disabled={submitting} onClick={() => post('approve')}>
            {submitting ? 'Invio…' : 'Approva'}
          </ActionBtn>
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
      style={{
        background: '#111318',
        border: `1px solid ${color}30`,
        borderRadius: 6,
        padding: '8px 10px',
        marginBottom: 6,
      }}
    >
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 3 }}>
        <span
          style={{
            fontSize: 9, fontFamily: 'monospace', color,
            background: `${color}20`, border: `1px solid ${color}60`,
            borderRadius: 3, padding: '1px 5px',
          }}
        >
          {item.severity}
        </span>
        <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#F0F1F6' }}>
          {item.category}
        </span>
      </div>
      <div style={{ fontSize: 11, color: '#8B8FA8', lineHeight: 1.5 }}>{item.text}</div>
      {item.fixSuggested && (
        <button
          onClick={() => setExpanded(o => !o)}
          style={{
            marginTop: 4, background: 'transparent', border: 'none',
            color: '#7C8CFF', fontSize: 10, cursor: 'pointer', padding: 0,
          }}
        >
          {expanded ? '▾' : '▸'} Fix suggerito
        </button>
      )}
      {expanded && item.fixSuggested && (
        <div
          style={{
            marginTop: 4, fontSize: 10, color: '#8B8FA8', fontFamily: 'monospace',
            background: '#0A0B0F', borderRadius: 4, padding: '6px 8px',
            whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          }}
        >
          {item.fixSuggested}
        </div>
      )}
    </div>
  )
}

function severityOrder(s: string) {
  return s === 'HIGH' ? 3 : s === 'MEDIUM' ? 2 : 1
}

function applyViolationHighlights(text: string, violations: Violation[]): string {
  if (!violations.length) return escapeHtml(text)
  const sorted = [...violations].sort((a, b) => a.start - b.start)
  let result = ''
  let cursor = 0
  for (const v of sorted) {
    if (v.start > cursor) result += escapeHtml(text.slice(cursor, v.start))
    result += `<mark style="background:rgba(202,138,4,0.25);border-radius:2px;" title="${escapeHtml(v.reason)}">${escapeHtml(text.slice(v.start, v.end))}</mark>`
    cursor = v.end
  }
  if (cursor < text.length) result += escapeHtml(text.slice(cursor))
  return `<pre style="white-space:pre-wrap;word-break:break-word;font-size:13px;line-height:1.8;color:#F0F1F6;font-family:inherit">${result}</pre>`
}

function escapeHtml(s: string) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function ActionBtn({
  children, onClick, disabled, variant,
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
        padding: '8px 16px', borderRadius: 6,
        fontSize: 12, fontFamily: 'monospace',
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
