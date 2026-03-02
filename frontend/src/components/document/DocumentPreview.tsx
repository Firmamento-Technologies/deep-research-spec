import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useRunStore } from '../../store/useRunStore'
import type { SectionResult } from '../../store/useRunStore'
import { ChapterExportMenu } from './ChapterExportMenu'
import { useAppStore } from '../../store/useAppStore'

export function DocumentPreview() {
  const { activeRun } = useRunStore()
  const { activeDocId } = useAppStore()
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)

  if (!activeRun) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 13,
          fontFamily: 'monospace',
          color: '#50536A',
        }}
      >
        Nessun documento selezionato.
      </div>
    )
  }

  const sections = activeRun.sections ?? []
  const approved = sections.filter(s => s.status === 'approved')

  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        background: '#0A0B0F',
      }}
    >
      {/* Document header */}
      <div
        style={{
          padding: '12px 20px',
          borderBottom: '1px solid #2A2D3A',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <div>
          <div style={{ fontSize: 14, color: '#F0F1F6', fontWeight: 600 }}>
            {activeRun.topic}
          </div>
          <div style={{ fontSize: 11, fontFamily: 'monospace', color: '#50536A', marginTop: 2 }}>
            {approved.length}/{sections.length} sezioni approvate
            {activeRun.cssScores && (
              <> • CSS
                <span style={{ color: activeRun.cssScores.content >= 0.65 ? '#22C55E' : '#EF4444' }}>
                  {activeRun.cssScores.content.toFixed(2)}
                </span>
              </>
            )}
          </div>
        </div>
        {activeDocId && (
          <ChapterExportMenu docId={activeDocId} label="Esporta tutto" />
        )}
      </div>

      {/* Sections accordion */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 20px' }}>
        {sections.length === 0 && (
          <div style={{ fontSize: 12, color: '#50536A', fontFamily: 'monospace', textAlign: 'center', marginTop: 48 }}>
            Nessuna sezione ancora approvata.
          </div>
        )}

        {sections.map((section, i) => (
          <SectionAccordion
            key={i}
            section={section}
            docId={activeDocId ?? ''}
            isExpanded={expandedIdx === i}
            onToggle={() => setExpandedIdx(expandedIdx === i ? null : i)}
          />
        ))}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Section accordion item                                               */
/* ------------------------------------------------------------------ */
interface SectionAccordionProps {
  section: SectionResult
  docId: string
  isExpanded: boolean
  onToggle: () => void
}

function SectionAccordion({ section, docId, isExpanded, onToggle }: SectionAccordionProps) {
  const statusColor =
    section.status === 'approved' ? '#22C55E' :
      section.status === 'failed' ? '#EF4444' :
        '#50536A'

  return (
    <div
      style={{
        border: '1px solid #2A2D3A',
        borderRadius: 8,
        marginBottom: 8,
        overflow: 'hidden',
      }}
    >
      {/* Accordion header */}
      <button
        onClick={onToggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          width: '100%',
          padding: '10px 14px',
          background: isExpanded ? '#1A1D27' : '#111318',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
          transition: 'background 0.15s',
        }}
      >
        <span style={{ fontSize: 11, color: '#50536A', fontFamily: 'monospace', flexShrink: 0 }}>
          {isExpanded ? '▾' : '▸'}
        </span>

        <span
          style={{
            fontSize: 10,
            fontFamily: 'monospace',
            color: '#50536A',
            flexShrink: 0,
          }}
        >
          §{section.idx + 1}
        </span>

        <span
          style={{
            flex: 1,
            fontSize: 13,
            color: '#F0F1F6',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {section.title}
        </span>

        {/* CSS badge */}
        {section.status === 'approved' && section.cssContent != null && (
          <CSSBadge value={section.cssContent} />
        )}

        {/* Word count */}
        {(section.wordsCount ?? section.wordCount) > 0 && (
          <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#50536A', flexShrink: 0 }}>
            {(section.wordsCount ?? section.wordCount).toLocaleString()}w
          </span>
        )}

        {/* Status dot */}
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: statusColor,
            flexShrink: 0,
          }}
        />

        {/* Export button */}
        {docId && (
          <div onClick={e => e.stopPropagation()}>
            <ChapterExportMenu docId={docId} sectionIdx={section.idx} label="" />
          </div>
        )}
      </button>

      {/* Accordion body — Markdown content */}
      {isExpanded && (
        <div
          style={{
            padding: '16px 20px',
            background: '#0A0B0F',
            borderTop: '1px solid #2A2D3A',
          }}
        >
          {section.content ? (
            <div
              style={{
                fontSize: 13,
                lineHeight: 1.8,
                color: '#F0F1F6',
                maxWidth: 720,
              }}
              className="prose-drs"
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {section.content}
              </ReactMarkdown>
            </div>
          ) : (
            <div style={{ fontSize: 12, color: '#50536A', fontFamily: 'monospace' }}>
              Contenuto non disponibile.
            </div>
          )}

          {/* Section metrics */}
          <div
            style={{
              display: 'flex',
              gap: 16,
              marginTop: 16,
              paddingTop: 12,
              borderTop: '1px solid #2A2D3A',
              fontSize: 11,
              fontFamily: 'monospace',
              color: '#50536A',
            }}
          >
            {section.cssContent != null && <Metric label="CSS Content" value={section.cssContent.toFixed(2)} color={section.cssContent >= 0.65 ? '#22C55E' : '#EF4444'} />}
            {section.cssStyle != null && <Metric label="CSS Style" value={section.cssStyle.toFixed(2)} color={section.cssStyle >= 0.80 ? '#22C55E' : '#EF4444'} />}
            {section.cssSource != null && <Metric label="CSS Source" value={section.cssSource.toFixed(2)} color="#8B8FA8" />}
            {(section.iterationsUsed ?? section.iterations) > 0 && <Metric label="Iterazioni" value={String(section.iterationsUsed ?? section.iterations)} color="#8B8FA8" />}
          </div>
        </div>
      )}
    </div>
  )
}

function CSSBadge({ value }: { value: number }) {
  const color = value >= 0.78 ? '#22C55E' : value >= 0.65 ? '#EAB308' : '#EF4444'
  return (
    <span
      style={{
        fontSize: 10,
        fontFamily: 'monospace',
        color,
        background: `${color}18`,
        border: `1px solid ${color}60`,
        borderRadius: 4,
        padding: '1px 5px',
        flexShrink: 0,
      }}
    >
      {value.toFixed(2)}
    </span>
  )
}

function Metric({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <span>
      <span style={{ color: '#50536A' }}>{label}: </span>
      <span style={{ color }}>{value}</span>
    </span>
  )
}
