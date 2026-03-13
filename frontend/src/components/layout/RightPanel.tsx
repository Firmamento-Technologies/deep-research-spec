import type { ReactNode } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'
import type { RunState } from '../../store/useRunStore'
import { PIPELINE_NODES, CLUSTER_COLORS } from '../../constants/pipeline-layout'
import { AgentLogPanel } from '../panel/AgentLogPanel'
import { TokenMeter } from '../panel/TokenMeter'
import { JuryVerdictGrid } from '../panel/JuryVerdictGrid'
import { SourceList } from '../panel/SourceList'
import { PayloadTree } from '../panel/PayloadTree'
import { AgentModelDropdown } from '../panel/AgentModelDropdown'

const JURY_NODES = new Set(['jury', 'r1', 'r2', 'r3', 'f1', 'f2', 'f3', 's1', 's2', 's3', 'aggregator'])
const RESEARCHER_NODES = new Set(['researcher', 'researcher_targeted'])
const REFLECTOR_NODES = new Set(['reflector'])

export function RightPanel() {
  const { rightPanelCollapsed, selectedNodeId, toggleRightPanel } = useAppStore()
  const { activeRun } = useRunStore()

  if (rightPanelCollapsed) {
    return (
      <div className="w-0 overflow-hidden transition-[width] duration-200 ease-out shrink-0" />
    )
  }

  return (
    <div className="hidden md:flex w-[320px] shrink-0 h-full bg-drs-s1 border-l border-drs-border flex-col overflow-hidden transition-[width] duration-200 ease-out">
      {/* Header */}
      <div className="h-[40px] flex items-center justify-between px-[12px] border-b border-drs-border shrink-0">
        <span className="text-[11px] font-mono text-drs-faint tracking-[1px]">
          {selectedNodeId ? selectedNodeId.toUpperCase().replace('_', ' ') : 'OVERVIEW'}
        </span>
        <button
          onClick={toggleRightPanel}
          className="bg-transparent border-none text-drs-faint cursor-pointer text-[14px] leading-none"
        >
          ×
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-[12px] flex flex-col gap-[12px]">
        {selectedNodeId && activeRun
          ? <NodeDetail nodeId={selectedNodeId} run={activeRun} />
          : <RunOverview run={activeRun} />
        }
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* RunOverview — shown when no node is selected                         */
/* ------------------------------------------------------------------ */
function RunOverview({ run }: { run: RunState | null }) {
  if (!run) {
    return (
      <div className="text-[12px] font-mono text-drs-faint">
        Nessun run attivo.
      </div>
    )
  }

  const budgetPct = run.maxBudget > 0
    ? Math.round((run.budgetSpent / run.maxBudget) * 100)
    : 0

  return (
    <div className="flex flex-col gap-[12px]">
      {/* Budget */}
      <Section label="BUDGET">
        <div className="text-[12px] font-mono text-drs-text">
          <span style={{
            color: budgetPct >= 90 ? '#EF4444' : budgetPct >= 70 ? '#EAB308' : '#22C55E'
          }}>
            ${run.budgetSpent.toFixed(3)}
          </span>
          <span className="text-drs-faint"> / ${run.maxBudget.toFixed(0)} ({budgetPct}%)</span>
        </div>
        <ProgressBar value={budgetPct} />
      </Section>

      {/* CSS Scores */}
      <Section label="CSS SCORES">
        <CSSScore label="Content" value={run.cssScores?.content ?? 0} threshold={0.65} />
        <CSSScore label="Style" value={run.cssScores?.style ?? 0} threshold={0.80} />
        <CSSScore label="Source" value={run.cssScores?.source ?? 0} threshold={0.70} />
      </Section>

      {/* Counters */}
      <Section label="CONTATORI">
        <Counter label="Sezione corrente" value={`${run.currentSection}/${run.totalSections}`} />
        <Counter label="Iterazione" value={`${run.currentIteration}`} />
        <Counter label="Stato" value={run.status} />
        <Counter label="Preset" value={run.qualityPreset} />
      </Section>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* NodeDetail — shown when a node is selected                           */
/* ------------------------------------------------------------------ */
function NodeDetail({ nodeId, run }: { nodeId: string; run: RunState }) {
  const nodeDef = PIPELINE_NODES.find(n => n.id === nodeId)
  const nodeState = run.nodes[nodeId]
  const status = nodeState?.status ?? 'waiting'
  const clusterColor = nodeDef ? CLUSTER_COLORS[nodeDef.cluster] : '#7C8CFF'
  const currentModel = nodeState?.model ?? nodeDef?.model ?? ''

  // Detect special node types
  const isJury = JURY_NODES.has(nodeId)
  const isResearcher = RESEARCHER_NODES.has(nodeId)
  const isReflector = REFLECTOR_NODES.has(nodeId)

  // Output text (real or mock)
  const outputText =
    typeof nodeState?.output === 'string'
      ? nodeState.output
      : nodeState?.output != null
        ? JSON.stringify(nodeState.output, null, 2).slice(0, 1000)
        : ''

  const outputPreview = outputText.length > 200
    ? outputText.slice(0, 200) + '…'
    : outputText

  return (
    <div className="flex flex-col gap-[12px]">
      {/* Node header */}
      <div
        className="rounded-[6px] p-[8px_12px]"
        style={{
          background: `${clusterColor}10`,
          border: `1px solid ${clusterColor}40`,
        }}
      >
        <div className="flex items-center justify-between gap-[8px]">
          <span className="text-[12px] font-mono text-drs-text font-bold">
            {nodeId.toUpperCase().replace(/_/g, ' ')}
          </span>
          <StatusBadge status={status} />
        </div>
        {currentModel && (
          <div className="flex items-center gap-[6px] mt-[6px]">
            <span className="text-[10px] font-mono text-drs-faint">Model:</span>
            <AgentModelDropdown nodeId={nodeId} currentModel={currentModel} />
          </div>
        )}
      </div>

      {/* JURY special case */}
      {isJury ? (
        <JuryVerdictGrid
          verdicts={
            run.juryVerdicts
              ?.flatMap((jv: any) => (jv as any).judges ?? [])
            ?? []
          }
        />
      ) : null}

      {/* REFLECTOR special case */}
      {isReflector && nodeState?.output ? (
        <ReflectorFeedback output={nodeState.output} />
      ) : null}

      {/* RESEARCHER special case */}
      {isResearcher && nodeState?.output ? (
        <SourceList sources={(nodeState.output as any)?.sources ?? []} />
      ) : null}

      {/* Live output */}
      {status === 'running' ? (
        <>
          <AgentLogPanel text={outputText} isLive />
          <TokenMeter
            tokensIn={nodeState?.tokensIn}
            tokensOut={nodeState?.tokensOut}
            costUsd={nodeState?.costUsd}
            isLive
          />
        </>
      ) : null}

      {/* Completed output */}
      {status === 'completed' && !isJury && !isResearcher && !isReflector && (
        <>
          <AgentLogPanel text={outputPreview} isLive={false} />
          <div className="text-[11px] font-mono text-drs-muted bg-drs-s1 border border-drs-border rounded-[6px] p-[6px_10px]">
            <span className="text-drs-faint">Latency:</span>{' '}
            {nodeState?.durationMs != null ? `${(nodeState.durationMs / 1000).toFixed(1)}s` : '—'}
            {'  •  '}
            <span className="text-drs-faint">In:</span>{' '}
            {nodeState?.tokensIn != null ? `${(nodeState.tokensIn / 1000).toFixed(1)}k` : '—'}
            {'  •  '}
            <span className="text-drs-faint">Out:</span>{' '}
            {nodeState?.tokensOut != null ? `${(nodeState.tokensOut / 1000).toFixed(1)}k` : '—'}
            {'  •  '}
            <span className="text-drs-yellow">
              {nodeState?.costUsd != null ? `$${nodeState.costUsd.toFixed(4)}` : '—'}
            </span>
          </div>
          <PayloadTree sections={buildPayloadSections(nodeState)} />
        </>
      )}

      {/* Error */}
      {status === 'failed' && nodeState?.error && (
        <div
          className="rounded-[6px] p-[8px_10px] text-[11px] font-mono text-drs-red"
          style={{ background: '#EF444415', border: '1px solid #EF444480' }}
        >
          {nodeState.error}
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Helpers                                                              */
/* ------------------------------------------------------------------ */
function ReflectorFeedback({ output }: { output: unknown }) {
  const items: Array<{ severity: string; category: string; text: string }> =
    (output as any)?.feedbackItems ?? []

  const severityColor = (s: string) =>
    s === 'HIGH' ? '#EF4444' : s === 'MEDIUM' ? '#F97316' : '#EAB308'

  return (
    <div className="flex flex-col gap-[8px]">
      <div className="text-[10px] font-mono text-drs-faint tracking-[1px]">
        FEEDBACK REFLECTOR
      </div>
      {items.length === 0 && (
        <div className="text-[11px] text-drs-faint font-mono">Nessun feedback.</div>
      )}
      {items.map((item, i) => (
        <div
          key={i}
          className="bg-drs-s1 rounded-[6px] p-[7px_10px]"
          style={{ border: `1px solid ${severityColor(item.severity)}40` }}
        >
          <div className="flex gap-[6px] items-center mb-[3px]">
            <span
              className="text-[9px] font-mono rounded-[3px] p-[1px_5px]"
              style={{
                color: severityColor(item.severity),
                background: `${severityColor(item.severity)}20`,
                border: `1px solid ${severityColor(item.severity)}60`,
              }}
            >
              {item.severity}
            </span>
            <span className="text-[11px] font-mono text-drs-text">
              {item.category}
            </span>
          </div>
          <div className="text-[11px] text-drs-muted leading-[1.5]">
            {item.text}
          </div>
        </div>
      ))}
    </div>
  )
}

function buildPayloadSections(nodeState: any) {
  if (!nodeState?.output || typeof nodeState.output !== 'object') return []
  const out = nodeState.output as Record<string, unknown>
  const sections = []
  if (out.system_prompt)
    sections.push({ label: 'system_prompt', tokens: estimateTokens(out.system_prompt), content: String(out.system_prompt) })
  if (out.context)
    sections.push({ label: 'context', tokens: estimateTokens(out.context), content: String(out.context) })
  if (out.outline_section)
    sections.push({ label: 'outline_section', tokens: estimateTokens(out.outline_section), content: String(out.outline_section) })
  return sections
}

function estimateTokens(val: unknown): number {
  return Math.round(String(val).length / 4)
}

function ProgressBar({ value }: { value: number }) {
  const color =
    value >= 90 ? '#EF4444' :
      value >= 70 ? '#EAB308' :
        '#22C55E'
  return (
    <div className="h-[4px] bg-drs-s2 rounded-[2px] mt-[6px] overflow-hidden">
      <div
        className="h-full rounded-[2px] transition-[width] duration-300"
        style={{
          width: `${Math.min(100, value)}%`,
          background: color,
        }}
      />
    </div>
  )
}

function CSSScore({ label, value, threshold }: { label: string; value: number; threshold: number }) {
  const pass = value >= threshold
  const color = pass ? '#22C55E' : value > 0 ? '#EF4444' : '#50536A'
  return (
    <div className="flex justify-between text-[11px] font-mono mb-[3px]">
      <span className="text-drs-muted">{label}</span>
      <span style={{ color }}>
        {value > 0 ? value.toFixed(2) : '—'}{pass ? ' ✅' : value > 0 ? ' ❌' : ''}
      </span>
    </div>
  )
}

function Counter({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between text-[11px] font-mono mb-[2px]">
      <span className="text-drs-faint">{label}</span>
      <span className="text-drs-text">{value}</span>
    </div>
  )
}

function Section({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="text-[10px] font-mono text-drs-faint tracking-[1px] mb-[6px]">
        {label}
      </div>
      {children}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; color: string }> = {
    waiting: { label: 'WAITING', color: '#50536A' },
    running: { label: 'RUNNING', color: '#22C55E' },
    completed: { label: 'DONE', color: '#4F6EF7' },
    failed: { label: 'FAILED', color: '#EF4444' },
    skipped: { label: 'SKIPPED', color: '#50536A' },
  }
  const { label, color } = map[status] ?? { label: status.toUpperCase(), color: '#8B8FA8' }
  return (
    <span
      className="text-[9px] font-mono rounded-[3px] p-[1px_6px] tracking-[0.5px]"
      style={{
        color,
        background: `${color}20`,
        border: `1px solid ${color}60`,
      }}
    >
      {label}
    </span>
  )
}
