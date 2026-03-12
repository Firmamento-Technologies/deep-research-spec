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
      <div className="flex-1 flex items-center justify-center text-[13px] font-mono text-drs-faint">
        Nessun documento selezionato.
      </div>
    )
  }

  const sections = activeRun.sections ?? []
  const approved = sections.filter(s => s.status === 'approved')

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-drs-bg">
      {/* Document header */}
      <div className="p-[12px_20px] border-b border-drs-border flex items-center justify-between shrink-0">
        <div>
          <div className="text-[14px] text-drs-text font-semibold">
            {activeRun.topic}
          </div>
          <div className="text-[11px] font-mono text-drs-faint mt-[2px]">
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
      <div className="flex-1 overflow-y-auto p-[12px_20px]">
        {sections.length === 0 && (
          <div className="text-[12px] text-drs-faint font-mono text-center mt-[48px]">
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
    <div className="border border-drs-border rounded-card mb-[8px] overflow-hidden">
      {/* Accordion header */}
      <button
        onClick={onToggle}
        className={`flex items-center gap-[10px] w-full p-[10px_14px] border-none cursor-pointer text-left transition-[background] duration-150 ${
          isExpanded ? 'bg-drs-s2' : 'bg-drs-s1'
        }`}
      >
        <span className="text-[11px] text-drs-faint font-mono shrink-0">
          {isExpanded ? '▾' : '▸'}
        </span>

        <span className="text-[10px] font-mono text-drs-faint shrink-0">
          §{section.idx + 1}
        </span>

        <span className="flex-1 text-[13px] text-drs-text overflow-hidden text-ellipsis whitespace-nowrap">
          {section.title}
        </span>

        {/* CSS badge */}
        {section.status === 'approved' && section.cssContent != null && (
          <CSSBadge value={section.cssContent} />
        )}

        {/* Word count */}
        {(section.wordsCount ?? section.wordCount) > 0 && (
          <span className="text-[10px] font-mono text-drs-faint shrink-0">
            {(section.wordsCount ?? section.wordCount).toLocaleString()}w
          </span>
        )}

        {/* Status dot */}
        <span
          className="w-[8px] h-[8px] rounded-full shrink-0"
          style={{ background: statusColor }}
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
        <div className="p-[16px_20px] bg-drs-bg border-t border-drs-border">
          {section.content ? (
            <div
              className="text-[13px] leading-[1.8] text-drs-text max-w-[720px] prose-drs"
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {section.content}
              </ReactMarkdown>
            </div>
          ) : (
            <div className="text-[12px] text-drs-faint font-mono">
              Contenuto non disponibile.
            </div>
          )}

          {/* Section metrics */}
          <div className="flex gap-[16px] mt-[16px] pt-[12px] border-t border-drs-border text-[11px] font-mono text-drs-faint">
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
      className="text-[10px] font-mono rounded-input shrink-0"
      style={{
        color,
        background: `${color}18`,
        border: `1px solid ${color}60`,
        padding: '1px 5px',
      }}
    >
      {value.toFixed(2)}
    </span>
  )
}

function Metric({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <span>
      <span className="text-drs-faint">{label}: </span>
      <span style={{ color }}>{value}</span>
    </span>
  )
}
