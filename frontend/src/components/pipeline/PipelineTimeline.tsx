// PipelineTimeline — vista principale del run DRS durante l'esecuzione.
// Sostituisce il grafo PipelineCanvas con una timeline leggibile in tempo reale.
//
// Layout:
//   RunHeader     (h-14)  — topic, budget, indicatore connessione
//   |── PhaseStepper (w-48)  — colonna sinistra, fasi lineari
//   |── ActivityFeed (flex)  — colonna destra, log SSE scrolling
//   CSSFooter     (h-10)  — score CSS live + sezioni approvate
//
// Dati: useRunStreamContext (T1) + useRunStore.

import { useRef, useEffect, useMemo } from 'react'
import { useRunStreamContext } from '../layout/AppShell'
import { useRunStore } from '../../store/useRunStore'
import { PHASE_LABEL } from '../../types/stream'
import type { RunPhase, ActivityEntry, ActivityEntryType } from '../../types/stream'

// ── Fasi in ordine di visualizzazione ──────────────────────────────────
const ORDERED_PHASES: RunPhase[] = [
  'preflight',
  'planning',
  'researching',
  'writing',
  'jury',
  'reflecting',
  'compressing',
  'publishing',
]

// ── Icone e colori per tipo di entry ────────────────────────────────
const TYPE_ICON: Record<ActivityEntryType, string> = {
  node_started:     '▶',
  node_completed:   '✓',
  thinking:         '…',
  section_started:  '§',
  section_approved: '✓✓',
  jury_pass:        '✓',
  jury_fail:        '✗',
  reflector:        '↺',
  budget:           'ⓢ',
  human_required:   '⚠',
  warning:          '⚠',
  error:            '✗',
  system:           '·',
  done:             '✓',
}

const TYPE_COLOR: Record<ActivityEntryType, string> = {
  node_started:     '#7C8CFF',
  node_completed:   '#22C55E',
  thinking:         '#8B8FA8',
  section_started:  '#06B6D4',
  section_approved: '#22C55E',
  jury_pass:        '#22C55E',
  jury_fail:        '#EAB308',
  reflector:        '#F97316',
  budget:           '#8B8FA8',
  human_required:   '#EAB308',
  warning:          '#EAB308',
  error:            '#EF4444',
  system:           '#50536A',
  done:             '#22C55E',
}

// ── Helper timestamp relativo ────────────────────────────────────────
function relTime(ts: Date): string {
  const s = Math.floor((Date.now() - ts.getTime()) / 1_000)
  if (s < 5)  return 'adesso'
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m`
  return `${Math.floor(m / 60)}h`
}

// ───────────────────────────────────────────────────────────────
// PipelineTimeline
// ───────────────────────────────────────────────────────────────
export function PipelineTimeline() {
  const { connected, activePhase, activityLog } = useRunStreamContext()
  const activeRun = useRunStore((s) => s.activeRun)

  // Deriva le fasi visitate dall'activity log
  const visitedPhases = useMemo(() => {
    const seen = new Set<RunPhase>()
    for (const e of activityLog) seen.add(e.phase)
    return seen
  }, [activityLog])

  if (!activeRun) {
    return (
      <div
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          height: '100%', color: '#50536A', fontSize: 12, fontFamily: 'monospace',
        }}
      >
        Nessun run attivo
      </div>
    )
  }

  return (
    <div
      style={{
        display: 'flex', flexDirection: 'column',
        height: '100%', overflow: 'hidden',
        background: '#0A0B0F',
      }}
    >
      {/* Header */}
      <RunHeader run={activeRun} connected={connected} />

      {/* Body — stepper + feed */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', borderTop: '1px solid #2A2D3A' }}>
        <PhaseStepper
          activePhase={activePhase}
          visitedPhases={visitedPhases}
          runStatus={activeRun.status}
          currentSection={activeRun.currentSection}
          totalSections={activeRun.totalSections}
        />
        <ActivityFeed log={activityLog} activePhase={activePhase} />
      </div>

      {/* Footer CSS */}
      <CSSFooter
        css={activeRun.cssScores}
        approvedCount={activeRun.sections.filter((s) => s.approved).length}
        totalSections={activeRun.totalSections}
      />
    </div>
  )
}

// ───────────────────────────────────────────────────────────────
// RunHeader
// ───────────────────────────────────────────────────────────────
type ActiveRun = NonNullable<ReturnType<typeof useRunStore>['activeRun']>

function RunHeader({ run, connected }: { run: ActiveRun; connected: boolean }) {
  const budgetPct  = run.maxBudget > 0
    ? Math.min(100, (run.budgetSpent / run.maxBudget) * 100)
    : 0
  const budgetColor =
    budgetPct >= 90 ? '#EF4444' :
    budgetPct >= 70 ? '#EAB308' : '#22C55E'

  const MAX_TOPIC = 80
  const topic = run.topic.length > MAX_TOPIC
    ? run.topic.slice(0, MAX_TOPIC) + '…'
    : run.topic

  return (
    <div
      style={{
        padding: '10px 16px 8px',
        borderBottom: '1px solid #2A2D3A',
        flexShrink: 0,
        background: '#111318',
      }}
    >
      {/* Riga 1: topic + connessione */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 6 }}>
        <span
          style={{
            fontSize: 13, color: '#F0F1F6', fontWeight: 600,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1,
          }}
          title={run.topic}
        >
          {topic}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
          <span
            style={{
              width: 6, height: 6, borderRadius: '50%',
              background: connected ? '#22C55E' : '#EF4444',
              display: 'inline-block',
              ...(connected ? {} : {}),
            }}
            className={connected ? 'animate-dot-pulse' : ''}
          />
          <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#50536A' }}>
            {connected ? 'stream attivo' : 'disconnesso'}
          </span>
        </div>
      </div>

      {/* Riga 2: budget bar + preset + status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {/* Budget */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}>
          <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#50536A', flexShrink: 0 }}>budget</span>
          <div
            style={{
              flex: 1, height: 3, background: '#1A1D27', borderRadius: 2, overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${budgetPct}%`,
                background: budgetColor,
                borderRadius: 2,
                transition: 'width 0.5s ease, background 0.3s',
              }}
            />
          </div>
          <span style={{ fontSize: 10, fontFamily: 'monospace', color: budgetColor, flexShrink: 0 }}>
            ${run.budgetSpent.toFixed(3)} / ${run.maxBudget}
          </span>
        </div>

        {/* Preset badge */}
        <span
          style={{
            fontSize: 9, fontFamily: 'monospace',
            color:   run.qualityPreset === 'Premium' ? '#22C55E'
                   : run.qualityPreset === 'Balanced' ? '#7C8CFF'
                   : '#EAB308',
            background: '#1A1D27',
            border: '1px solid #2A2D3A',
            borderRadius: 3, padding: '1px 6px',
          }}
        >
          {run.qualityPreset.toUpperCase()}
        </span>

        {/* Status */}
        <span
          style={{
            fontSize: 9, fontFamily: 'monospace',
            color: run.status === 'running' ? '#22C55E'
                 : run.status === 'completed' ? '#7C8CFF'
                 : run.status === 'failed' ? '#EF4444'
                 : run.status === 'awaiting_approval' ? '#EAB308'
                 : '#50536A',
          }}
        >
          {run.status}
        </span>
      </div>
    </div>
  )
}

// ───────────────────────────────────────────────────────────────
// PhaseStepper
// ───────────────────────────────────────────────────────────────
interface PhaseStepperProps {
  activePhase:    RunPhase
  visitedPhases:  Set<RunPhase>
  runStatus:      string
  currentSection: number
  totalSections:  number
}

function PhaseStepper({
  activePhase, visitedPhases, runStatus, currentSection, totalSections,
}: PhaseStepperProps) {
  const isDone   = runStatus === 'completed'
  const isFailed = runStatus === 'failed'

  return (
    <div
      style={{
        width: 192,
        flexShrink: 0,
        borderRight: '1px solid #2A2D3A',
        padding: '16px 12px',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 0,
      }}
    >
      <div
        style={{
          fontSize: 9, fontFamily: 'monospace', color: '#50536A',
          letterSpacing: 1, marginBottom: 12,
        }}
      >
        PIPELINE
      </div>

      {ORDERED_PHASES.map((phase, i) => {
        const isActive  = activePhase === phase
        const isVisited = visitedPhases.has(phase) && !isActive
        const isLoop    = ['researching', 'writing', 'jury', 'reflecting'].includes(phase)

        let dotColor = '#2A2D3A'      // upcoming
        let textColor = '#50536A'
        let dotBg = 'transparent'

        if (isDone) {
          dotColor = '#22C55E'
          dotBg    = '#22C55E'
          textColor = '#22C55E'
        } else if (isFailed && isActive) {
          dotColor  = '#EF4444'
          dotBg     = '#EF4444'
          textColor = '#EF4444'
        } else if (isActive) {
          dotColor  = '#7C8CFF'
          dotBg     = '#7C8CFF'
          textColor = '#F0F1F6'
        } else if (isVisited) {
          dotColor  = '#22C55E'
          dotBg     = '#22C55E22'
          textColor = '#8B8FA8'
        }

        return (
          <div key={phase}>
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 8,
                padding: '5px 4px',
                borderRadius: 4,
                background: isActive ? '#7C8CFF10' : 'transparent',
                transition: 'background 0.2s',
              }}
            >
              {/* Dot */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 2 }}>
                <div
                  style={{
                    width: 8, height: 8, borderRadius: '50%',
                    border: `1.5px solid ${dotColor}`,
                    background: dotBg,
                    flexShrink: 0,
                    transition: 'all 0.3s',
                  }}
                  className={isActive && !isDone && !isFailed ? 'animate-dot-pulse' : ''}
                />
                {/* Connettore verticale tra fasi */}
                {i < ORDERED_PHASES.length - 1 && (
                  <div
                    style={{
                      width: 1.5,
                      height: 20,
                      background: isVisited || isDone ? '#22C55E40' : '#2A2D3A',
                      margin: '2px 0',
                      transition: 'background 0.3s',
                    }}
                  />
                )}
              </div>

              {/* Testo fase */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: isActive ? 600 : 400,
                    color: textColor,
                    transition: 'color 0.2s',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {PHASE_LABEL[phase]}
                </div>

                {/* Sotto-info per fasi in loop */}
                {isActive && isLoop && totalSections > 0 && (
                  <div style={{ fontSize: 10, fontFamily: 'monospace', color: '#50536A', marginTop: 1 }}>
                    sez. {currentSection}/{totalSections}
                  </div>
                )}
                {isLoop && (
                  <div style={{ fontSize: 9, color: '#50536A', marginTop: 1 }}>loop</div>
                )}
              </div>
            </div>
          </div>
        )
      })}

      {/* Done / Failed finale */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '5px 4px', marginTop: 4,
        }}
      >
        <div
          style={{
            width: 8, height: 8, borderRadius: 2,
            background: isDone ? '#22C55E'
                      : isFailed ? '#EF4444'
                      : '#2A2D3A',
            border: `1.5px solid ${
              isDone ? '#22C55E' : isFailed ? '#EF4444' : '#2A2D3A'
            }`,
            transition: 'all 0.3s',
          }}
        />
        <span
          style={{
            fontSize: 11,
            color: isDone ? '#22C55E' : isFailed ? '#EF4444' : '#50536A',
          }}
        >
          {isDone ? 'Completato' : isFailed ? 'Errore' : 'Fine'}
        </span>
      </div>
    </div>
  )
}

// ───────────────────────────────────────────────────────────────
// ActivityFeed
// ───────────────────────────────────────────────────────────────
interface ActivityFeedProps {
  log:         ActivityEntry[]
  activePhase: RunPhase
}

function ActivityFeed({ log, activePhase }: ActivityFeedProps) {
  const listRef = useRef<HTMLDivElement>(null)

  // Scroll to top quando arrivano nuove entry (log è newest-first)
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = 0
    }
  }, [log.length])

  return (
    <div
      style={{
        flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}
    >
      {/* Header feed */}
      <div
        style={{
          padding: '8px 14px 6px',
          borderBottom: '1px solid #2A2D3A',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 9, fontFamily: 'monospace', color: '#50536A', letterSpacing: 1 }}>
          ATTIVITÀ IN TEMPO REALE
        </span>
        {activePhase !== 'idle' && activePhase !== 'done' && activePhase !== 'failed' && (
          <span
            style={{
              fontSize: 10, fontFamily: 'monospace',
              color: '#7C8CFF',
              display: 'flex', alignItems: 'center', gap: 4,
            }}
          >
            <span
              style={{ width: 5, height: 5, borderRadius: '50%', background: '#7C8CFF', display: 'inline-block' }}
              className="animate-dot-pulse"
            />
            {PHASE_LABEL[activePhase]}
          </span>
        )}
      </div>

      {/* Lista eventi */}
      <div
        ref={listRef}
        style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}
      >
        {log.length === 0 && (
          <div
            style={{
              padding: '32px 16px', textAlign: 'center',
              color: '#50536A', fontSize: 12, fontFamily: 'monospace',
            }}
          >
            In attesa degli eventi…
          </div>
        )}

        {log.map((entry) => (
          <ActivityRow key={entry.id} entry={entry} />
        ))}
      </div>
    </div>
  )
}

function ActivityRow({ entry }: { entry: ActivityEntry }) {
  const color    = TYPE_COLOR[entry.type]
  const icon     = TYPE_ICON[entry.type]
  const isThink  = entry.type === 'thinking'
  const isError  = entry.type === 'error'
  const isSectionEvent = entry.type === 'section_started' || entry.type === 'section_approved'

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 8,
        padding: '4px 14px',
        borderLeft: isSectionEvent ? `2px solid ${color}` : '2px solid transparent',
        background: isError ? '#EF444408' : isSectionEvent ? `${color}08` : 'transparent',
        transition: 'background 0.2s',
      }}
    >
      {/* Icona */}
      <span
        style={{
          fontSize: 10,
          fontFamily: 'monospace',
          color,
          flexShrink: 0,
          paddingTop: 1,
          minWidth: 14,
          textAlign: 'center',
        }}
        className={isThink ? 'animate-dot-pulse' : ''}
      >
        {icon}
      </span>

      {/* Testo */}
      <span
        style={{
          fontSize: 11,
          color: isError ? '#EF4444' : isThink ? '#8B8FA8' : isSectionEvent ? '#F0F1F6' : '#8B8FA8',
          fontStyle: isThink ? 'italic' : 'normal',
          flex: 1,
          lineHeight: 1.45,
          wordBreak: 'break-word',
        }}
      >
        {entry.label}
      </span>

      {/* Timestamp */}
      <span
        style={{
          fontSize: 9,
          fontFamily: 'monospace',
          color: '#50536A',
          flexShrink: 0,
          paddingTop: 2,
        }}
      >
        {relTime(entry.ts)}
      </span>
    </div>
  )
}

// ───────────────────────────────────────────────────────────────
// CSSFooter
// ───────────────────────────────────────────────────────────────
interface CSSFooterProps {
  css:            { content: number; style: number; source: number }
  approvedCount:  number
  totalSections:  number
}

function CSSScore({ label, value, threshold }: { label: string; value: number; threshold: number }) {
  const hasValue = value > 0
  const pass = hasValue && value >= threshold
  const fail = hasValue && value < threshold
  const color = pass ? '#22C55E' : fail ? '#EF4444' : '#50536A'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#50536A' }}>{label}</span>
      <span style={{ fontSize: 11, fontFamily: 'monospace', color, fontWeight: 600 }}>
        {hasValue ? value.toFixed(2) : '—'}
      </span>
      {pass && <span style={{ fontSize: 9, color: '#22C55E' }}>✓</span>}
      {fail && <span style={{ fontSize: 9, color: '#EF4444' }}>✗</span>}
    </div>
  )
}

function CSSFooter({ css, approvedCount, totalSections }: CSSFooterProps) {
  return (
    <div
      style={{
        height: 38, flexShrink: 0,
        borderTop: '1px solid #2A2D3A',
        background: '#111318',
        display: 'flex',
        alignItems: 'center',
        gap: 20,
        padding: '0 16px',
        overflow: 'hidden',
      }}
    >
      <span style={{ fontSize: 9, fontFamily: 'monospace', color: '#50536A', letterSpacing: 1, flexShrink: 0 }}>
        CSS
      </span>
      <CSSScore label="C" value={css.content} threshold={0.65} />
      <CSSScore label="S" value={css.style}   threshold={0.80} />
      <CSSScore label="F" value={css.source}  threshold={0.70} />

      <div style={{ flex: 1 }} />

      {totalSections > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#50536A' }}>sezioni</span>
          <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#F0F1F6' }}>
            {approvedCount}
            <span style={{ color: '#50536A' }}>/{totalSections}</span>
          </span>
          {/* Mini progress bar */}
          <div style={{ width: 60, height: 3, background: '#1A1D27', borderRadius: 2, overflow: 'hidden' }}>
            <div
              style={{
                height: '100%',
                width: `${totalSections > 0 ? (approvedCount / totalSections) * 100 : 0}%`,
                background: '#7C8CFF',
                borderRadius: 2,
                transition: 'width 0.4s ease',
              }}
            />
          </div>
        </div>
      )}
    </div>
  )
}
