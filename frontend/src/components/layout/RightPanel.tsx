import React from 'react'
import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'
import { PIPELINE_NODES, CLUSTER_COLORS } from '../../constants/pipeline-layout'
import { AgentLogPanel } from '../panel/AgentLogPanel'
import { TokenMeter } from '../panel/TokenMeter'
import { JuryVerdictGrid } from '../panel/JuryVerdictGrid'
import { SourceList } from '../panel/SourceList'
import { PayloadTree } from '../panel/PayloadTree'
import { AgentModelDropdown } from '../panel/AgentModelDropdown'

const JURY_NODES = new Set(['jury', 'r1','r2','r3','f1','f2','f3','s1','s2','s3','aggregator'])
const RESEARCHER_NODES = new Set(['researcher', 'researcher_targeted'])
const REFLECTOR_NODES = new Set(['reflector'])

export function RightPanel() {
  const { rightPanelCollapsed, selectedNodeId, toggleRightPanel } = useAppStore()
  const { activeRun } = useRunStore()

  if (rightPanelCollapsed) {
    return (
      <div
        style={{
          width: 0,
          overflow: 'hidden',
          transition: 'width 200ms ease',
          flexShrink: 0,
        }}
      />
    )
  }

  return (
    <div
      style={{
        width: 320,
        flexShrink: 0,
        height: '100%',
        background: '#111318',
        borderLeft: '1px solid #2A2D3A',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        transition: 'width 200ms ease',
      }}
    >
      {/* Header */}
      <div
        style={{
          height: 40,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 12px',
          borderBottom: '1px solid #2A2D3A',
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#50536A', letterSpacing: 1 }}>
          {selectedNodeId ? selectedNodeId.toUpperCase().replace('_', ' ') : 'OVERVIEW'}
        </span>
        <button
          onClick={toggleRightPanel}
          style={{
            background: 'transparent',
            border: 'none',
            color: '#50536A',
            cursor: 'pointer',
            fontSize: 14,
            lineHeight: 1,
          }}
        >
          ×
        </button>
      </div>

      {/* Content */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
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
function RunOverview({ run }: { run: ReturnType<typeof useRunStore>['activeRun'] }) {
  if (!run) {
    return (
      <div style={{ fontSize: 12, fontFamily: 'monospace', color: '#50536A' }}>
        Nessun run attivo.
      </div>
    )
  }

  const budgetPct = run.maxBudget > 0
    ? Math.round((run.budgetSpent / run.maxBudget) * 100)
    : 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Budget */}
      <Section label="BUDGET">
        <div style={{ fontSize: 12, fontFamily: 'monospace', color: '#F0F1F6' }}>
          <span style={{
            color: budgetPct >= 90 ? '#EF4444' : budgetPct >= 70 ? '#EAB308' : '#22C55E'
          }}>
            ${run.budgetSpent.toFixed(3)}
          </span>
          <span style={{ color: '#50536A' }}> / ${run.maxBudget.toFixed(0)} ({budgetPct}%)</span>
        </div>
        <ProgressBar value={budgetPct} />
      </Section>

      {/* CSS Scores */}
      <Section label="CSS SCORES">
        <CSSScore label="Content" value={run.cssScores?.content ?? 0} threshold={0.65} />
        <CSSScore label="Style"   value={run.cssScores?.style   ?? 0} threshold={0.80} />
        <CSSScore label="Source"  value={run.cssScores?.source  ?? 0} threshold={0.70} />
      </Section>

      {/* Counters */}
      <Section label="CONTATORI">
        <Counter label="Sezione corrente"  value={`${run.currentSection}/${run.totalSections}`} />
        <Counter label="Iterazione"        value={`${run.currentIteration}`} />
        <Counter label="Stato"             value={run.status} />
        <Counter label="Preset"            value={run.qualityPreset} />
      </Section>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* NodeDetail — shown when a node is selected                           */
/* ------------------------------------------------------------------ */
function NodeDetail({ nodeId, run }: { nodeId: string; run: NonNullable<ReturnType<typeof useRunStore>['activeRun']> }) {
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Node header */}
      <div
        style={{
          background: `${clusterColor}10`,
          border: `1px solid ${clusterColor}40`,
          borderRadius: 6,
          padding: '8px 12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <span style={{ fontSize: 12, fontFamily: 'monospace', color: '#F0F1F6', fontWeight: 700 }}>
            {nodeId.toUpperCase().replace(/_/g, ' ')}
          </span>
          <StatusBadge status={status} />
        </div>
        {currentModel && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
            <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#50536A' }}>Model:</span>
            <AgentModelDropdown nodeId={nodeId} currentModel={currentModel} />
          </div>
        )}
      </div>

      {/* JURY special case */}
      {isJury && (
        <JuryVerdictGrid
          verdicts={
            run.juryVerdicts
              ?.flatMap(jv => (jv as any).judges ?? [])
            ?? []
          }
        />
      )}

      {/* REFLECTOR special case */}
      {isReflector && nodeState?.output && (
        <ReflectorFeedback output={nodeState.output} />
      )}

      {/* RESEARCHER special case */}
      {isResearcher && nodeState?.output && (
        <SourceList sources={(nodeState.output as any)?.sources ?? []} />
      )}

      {/* Live output */}
      {status === 'running' && (
        <>
          <AgentLogPanel text={outputText} isLive />
          <TokenMeter
            tokensIn={nodeState?.tokensIn}
            tokensOut={nodeState?.tokensOut}
            costUsd={nodeState?.costUsd}
            isLive
          />
        </>
      )}

      {/* Completed output */}
      {status === 'completed' && !isJury && !isResearcher && !isReflector && (
        <>
          <AgentLogPanel text={outputPreview} isLive={false} />
          <div
            style={{
              fontSize: 11,
              fontFamily: 'monospace',
              color: '#8B8FA8',
              background: '#111318',
              border: '1px solid #2A2D3A',
              borderRadius: 6,
              padding: '6px 10px',
            }}
          >
            <span style={{ color: '#50536A' }}>Latency:</span>{' '}
            {nodeState?.durationMs != null ? `${(nodeState.durationMs / 1000).toFixed(1)}s` : '—'}
            {'  •  '}
            <span style={{ color: '#50536A' }}>In:</span>{' '}
            {nodeState?.tokensIn != null ? `${(nodeState.tokensIn / 1000).toFixed(1)}k` : '—'}
            {'  •  '}
            <span style={{ color: '#50536A' }}>Out:</span>{' '}
            {nodeState?.tokensOut != null ? `${(nodeState.tokensOut / 1000).toFixed(1)}k` : '—'}
            {'  •  '}
            <span style={{ color: '#EAB308' }}>
              {nodeState?.costUsd != null ? `$${nodeState.costUsd.toFixed(4)}` : '—'}
            </span>
          </div>
          <PayloadTree sections={buildPayloadSections(nodeState)} />
        </>
      )}

      {/* Error */}
      {status === 'failed' && nodeState?.error && (
        <div
          style={{
            background: '#EF444415',
            border: '1px solid #EF444480',
            borderRadius: 6,
            padding: '8px 10px',
            fontSize: 11,
            fontFamily: 'monospace',
            color: '#EF4444',
          }}
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 10, fontFamily: 'monospace', color: '#50536A', letterSpacing: 1 }}>
        FEEDBACK REFLECTOR
      </div>
      {items.length === 0 && (
        <div style={{ fontSize: 11, color: '#50536A', fontFamily: 'monospace' }}>Nessun feedback.</div>
      )}
      {items.map((item, i) => (
        <div
          key={i}
          style={{
            background: '#111318',
            border: `1px solid ${severityColor(item.severity)}40`,
            borderRadius: 6,
            padding: '7px 10px',
          }}
        >
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 3 }}>
            <span
              style={{
                fontSize: 9,
                fontFamily: 'monospace',
                color: severityColor(item.severity),
                background: `${severityColor(item.severity)}20`,
                border: `1px solid ${severityColor(item.severity)}60`,
                borderRadius: 3,
                padding: '1px 5px',
              }}
            >
              {item.severity}
            </span>
            <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#F0F1F6' }}>
              {item.category}
            </span>
          </div>
          <div style={{ fontSize: 11, color: '#8B8FA8', lineHeight: 1.5 }}>
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
    <div
      style={{
        height: 4,
        background: '#1A1D27',
        borderRadius: 2,
        marginTop: 6,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          height: '100%',
          width: `${Math.min(100, value)}%`,
          background: color,
          borderRadius: 2,
          transition: 'width 0.3s',
        }}
      />
    </div>
  )
}

function CSSScore({ label, value, threshold }: { label: string; value: number; threshold: number }) {
  const pass = value >= threshold
  const color = pass ? '#22C55E' : value > 0 ? '#EF4444' : '#50536A'
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, fontFamily: 'monospace', marginBottom: 3 }}>
      <span style={{ color: '#8B8FA8' }}>{label}</span>
      <span style={{ color }}>
        {value > 0 ? value.toFixed(2) : '—'}{pass ? ' ✅' : value > 0 ? ' ❌' : ''}
      </span>
    </div>
  )
}

function Counter({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, fontFamily: 'monospace', marginBottom: 2 }}>
      <span style={{ color: '#50536A' }}>{label}</span>
      <span style={{ color: '#F0F1F6' }}>{value}</span>
    </div>
  )
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 10, fontFamily: 'monospace', color: '#50536A', letterSpacing: 1, marginBottom: 6 }}>
        {label}
      </div>
      {children}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; color: string }> = {
    waiting:   { label: 'WAITING',   color: '#50536A' },
    running:   { label: 'RUNNING',   color: '#22C55E' },
    completed: { label: 'DONE',      color: '#4F6EF7' },
    failed:    { label: 'FAILED',    color: '#EF4444' },
    skipped:   { label: 'SKIPPED',  color: '#50536A' },
  }
  const { label, color } = map[status] ?? { label: status.toUpperCase(), color: '#8B8FA8' }
  return (
    <span
      style={{
        fontSize: 9,
        fontFamily: 'monospace',
        color,
        background: `${color}20`,
        border: `1px solid ${color}60`,
        borderRadius: 3,
        padding: '1px 6px',
        letterSpacing: 0.5,
      }}
    >
      {label}
    </span>
  )
}
