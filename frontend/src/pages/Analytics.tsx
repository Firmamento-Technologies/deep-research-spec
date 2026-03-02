import React, { useEffect, useState, useCallback } from 'react'
import {
  LineChart, Line,
  BarChart, Bar,
  ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell,
} from 'recharts'

// ------------------------------------------------------------------ //
// Types
// ------------------------------------------------------------------ //
interface AnalyticsData {
  kpis: {
    total_runs: number
    avg_cost_per_doc: number
    total_words: number
    avg_css_composite: number
    first_iteration_success_rate: number
  }
  css_over_time: Array<{ date: string; value: number; doc_id: string; topic: string }>
  cost_by_preset: Array<{ preset: string; avg_cost: number; count: number }>
  css_vs_cost: Array<{ css: number; cost: number; preset: string; topic: string }>
  iterations_heatmap: Array<{ section: number; iterations: number; count: number }>
}

const PRESET_OPTIONS = ['Economy', 'Balanced', 'Premium']

const PRESET_COLORS: Record<string, string> = {
  Economy:  '#22C55E',
  Balanced: '#7C8CFF',
  Premium:  '#A855F7',
}

// ------------------------------------------------------------------ //
// Analytics page
// ------------------------------------------------------------------ //
export function Analytics() {
  const [from, setFrom]         = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 30); return d.toISOString().slice(0, 10)
  })
  const [to, setTo]             = useState(() => new Date().toISOString().slice(0, 10))
  const [presets, setPresets]   = useState<string[]>([])
  const [keyword, setKeyword]   = useState('')
  const [data, setData]         = useState<AnalyticsData | null>(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ from, to })
      if (presets.length) params.set('preset', presets.join(','))
      if (keyword) params.set('keyword', keyword)
      const res = await fetch(`/api/analytics?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setData(json)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [from, to, presets, keyword])

  useEffect(() => { fetchData() }, [fetchData])

  const togglePreset = (p: string) =>
    setPresets(prev => prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p])

  return (
    <div
      style={{
        flex: 1,
        background: '#0A0B0F',
        overflowY: 'auto',
        padding: '20px 28px',
        display: 'flex',
        flexDirection: 'column',
        gap: 24,
      }}
    >
      <div style={{ fontSize: 18, color: '#F0F1F6', fontWeight: 700 }}>Analytics</div>

      {/* Filter bar */}
      <FilterBar
        from={from} to={to} presets={presets} keyword={keyword}
        onFrom={setFrom} onTo={setTo} onTogglePreset={togglePreset}
        onKeyword={setKeyword} onRefresh={fetchData}
      />

      {error && (
        <div style={{
          background: '#EF444415', border: '1px solid #EF4444', borderRadius: 6,
          padding: '8px 12px', fontSize: 12, color: '#EF4444', fontFamily: 'monospace',
        }}>
          Errore: {error}
        </div>
      )}

      {loading && !data && (
        <div style={{ color: '#50536A', fontSize: 12, fontFamily: 'monospace' }}>Caricamento dati…</div>
      )}

      {data && (
        <>
          {/* KPI cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
            <KpiCard label="Runs completati"    value={data.kpis.total_runs.toString()} />
            <KpiCard label="Costo medio/doc"    value={`$${data.kpis.avg_cost_per_doc.toFixed(2)}`} color="#EAB308" />
            <KpiCard label="Parole totali"      value={data.kpis.total_words.toLocaleString()} color="#7C8CFF" />
            <KpiCard label="CSS medio"          value={data.kpis.avg_css_composite.toFixed(3)} color={data.kpis.avg_css_composite >= 0.70 ? '#22C55E' : '#EF4444'} />
            <KpiCard label="Successo 1ª iter." value={`${(data.kpis.first_iteration_success_rate * 100).toFixed(1)}%`} color="#22C55E" />
          </div>

          {/* 2×2 Chart grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <ChartCard title="CSS Score nel Tempo">
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={data.css_over_time} margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2A2D3A" vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: '#50536A', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 1]} tick={{ fill: '#50536A', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke="#7C8CFF"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, fill: '#7C8CFF' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Costo per Preset">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={data.cost_by_preset} margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2A2D3A" vertical={false} />
                  <XAxis dataKey="preset" tick={{ fill: '#50536A', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#50536A', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="avg_cost" radius={[3, 3, 0, 0]}>
                    {data.cost_by_preset.map((entry, i) => (
                      <Cell key={i} fill={PRESET_COLORS[entry.preset] ?? '#7C8CFF'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="CSS vs Costo">
              <ResponsiveContainer width="100%" height={220}>
                <ScatterChart margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2A2D3A" />
                  <XAxis dataKey="cost"  name="Costo ($)"   tick={{ fill: '#50536A', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis dataKey="css"   name="CSS"   domain={[0, 1]} tick={{ fill: '#50536A', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    content={({ payload }) => {
                      if (!payload?.length) return null
                      const d = payload[0]?.payload
                      return (
                        <div style={{ background: '#111318', border: '1px solid #2A2D3A', borderRadius: 6, padding: '6px 10px', fontSize: 11 }}>
                          <div style={{ color: '#F0F1F6' }}>{d?.topic}</div>
                          <div style={{ color: '#8B8FA8' }}>CSS: {d?.css?.toFixed(3)}  Costo: ${d?.cost?.toFixed(3)}</div>
                          <div style={{ color: PRESET_COLORS[d?.preset] ?? '#8B8FA8' }}>{d?.preset}</div>
                        </div>
                      )
                    }}
                  />
                  {PRESET_OPTIONS.map(preset => (
                    <Scatter
                      key={preset}
                      name={preset}
                      data={data.css_vs_cost.filter(d => d.preset === preset)}
                      fill={PRESET_COLORS[preset]}
                    />
                  ))}
                  <Legend
                    formatter={(value) => <span style={{ color: '#8B8FA8', fontSize: 10 }}>{value}</span>}
                    wrapperStyle={{ paddingTop: 8 }}
                  />
                </ScatterChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Iterazioni per Sezione (Heatmap)">
              <IterationsHeatmap data={data.iterations_heatmap} />
            </ChartCard>
          </div>
        </>
      )}
    </div>
  )
}

// ------------------------------------------------------------------ //
// Filter bar
// ------------------------------------------------------------------ //
function FilterBar({
  from, to, presets, keyword,
  onFrom, onTo, onTogglePreset, onKeyword, onRefresh,
}: {
  from: string; to: string; presets: string[]; keyword: string
  onFrom: (v: string) => void
  onTo: (v: string) => void
  onTogglePreset: (p: string) => void
  onKeyword: (v: string) => void
  onRefresh: () => void
}) {
  const inputStyle: React.CSSProperties = {
    background: '#111318',
    border: '1px solid #2A2D3A',
    borderRadius: 4,
    color: '#F0F1F6',
    fontSize: 12,
    fontFamily: 'monospace',
    padding: '5px 10px',
    outline: 'none',
  }
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
      <span style={{ fontSize: 11, color: '#50536A', fontFamily: 'monospace' }}>DA</span>
      <input type="date" value={from} onChange={e => onFrom(e.target.value)} style={inputStyle} />
      <span style={{ fontSize: 11, color: '#50536A', fontFamily: 'monospace' }}>A</span>
      <input type="date" value={to} onChange={e => onTo(e.target.value)} style={inputStyle} />

      <div style={{ display: 'flex', gap: 6 }}>
        {PRESET_OPTIONS.map(p => {
          const active = presets.includes(p)
          const color = PRESET_COLORS[p]
          return (
            <button
              key={p}
              onClick={() => onTogglePreset(p)}
              style={{
                padding: '4px 10px', borderRadius: 4, fontSize: 11, fontFamily: 'monospace',
                cursor: 'pointer',
                background: active ? `${color}20` : 'transparent',
                border: `1px solid ${active ? color : '#2A2D3A'}`,
                color: active ? color : '#50536A',
              }}
            >
              {p}
            </button>
          )
        })}
      </div>

      <input
        value={keyword}
        onChange={e => onKeyword(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') onRefresh() }}
        placeholder="Cerca topic…"
        style={{ ...inputStyle, width: 180 }}
      />

      <button
        onClick={onRefresh}
        style={{
          background: '#7C8CFF',
          border: 'none',
          borderRadius: 4,
          color: '#0A0B0F',
          fontSize: 12,
          fontFamily: 'monospace',
          padding: '5px 14px',
          cursor: 'pointer',
          fontWeight: 700,
        }}
      >
        Aggiorna
      </button>
    </div>
  )
}

// ------------------------------------------------------------------ //
// KPI card
// ------------------------------------------------------------------ //
function KpiCard({ label, value, color = '#F0F1F6' }: { label: string; value: string; color?: string }) {
  return (
    <div
      style={{
        background: '#111318',
        border: '1px solid #2A2D3A',
        borderRadius: 8,
        padding: '14px 16px',
      }}
    >
      <div style={{ fontSize: 10, fontFamily: 'monospace', color: '#50536A', letterSpacing: 1, marginBottom: 6 }}>
        {label.toUpperCase()}
      </div>
      <div style={{ fontSize: 22, fontFamily: 'monospace', color, fontWeight: 700, lineHeight: 1 }}>
        {value}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ //
// Chart card wrapper
// ------------------------------------------------------------------ //
function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: '#111318',
        border: '1px solid #2A2D3A',
        borderRadius: 8,
        padding: '14px 16px',
      }}
    >
      <div style={{ fontSize: 11, fontFamily: 'monospace', color: '#8B8FA8', marginBottom: 12, letterSpacing: 0.5 }}>
        {title}
      </div>
      {children}
    </div>
  )
}

// ------------------------------------------------------------------ //
// Custom Recharts tooltip
// ------------------------------------------------------------------ //
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div
      style={{
        background: '#111318',
        border: '1px solid #2A2D3A',
        borderRadius: 6,
        padding: '6px 10px',
        fontSize: 11,
        fontFamily: 'monospace',
      }}
    >
      {label && <div style={{ color: '#8B8FA8', marginBottom: 4 }}>{label}</div>}
      {payload.map((p: any, i: number) => (
        <div key={i} style={{ color: p.color ?? '#F0F1F6' }}>
          {p.name ? `${p.name}: ` : ''}{typeof p.value === 'number' ? p.value.toFixed(3) : p.value}
        </div>
      ))}
    </div>
  )
}

// ------------------------------------------------------------------ //
// Iterations heatmap (custom cell grid)
// ------------------------------------------------------------------ //
function IterationsHeatmap({
  data,
}: {
  data: Array<{ section: number; iterations: number; count: number }>
}) {
  if (!data.length) {
    return (
      <div style={{ height: 220, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontSize: 12, color: '#50536A', fontFamily: 'monospace' }}>Nessun dato.</span>
      </div>
    )
  }

  const maxSection   = Math.max(...data.map(d => d.section),   0)
  const maxIteration = Math.max(...data.map(d => d.iterations), 0)
  const maxCount     = Math.max(...data.map(d => d.count),      1)

  const lookup = new Map(data.map(d => [`${d.section}:${d.iterations}`, d.count]))

  const CELL_W = Math.min(28, Math.floor(420 / Math.max(maxSection + 1, 1)))
  const CELL_H = 18

  return (
    <div style={{ overflowX: 'auto', height: 220 }}>
      <div style={{ display: 'inline-flex', flexDirection: 'column', gap: 2, padding: '4px 0' }}>
        {/* Y axis label */}
        {Array.from({ length: maxIteration + 1 }, (_, iter) => (
          <div key={iter} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 9, fontFamily: 'monospace', color: '#50536A', width: 16, textAlign: 'right', flexShrink: 0 }}>
              {iter + 1}
            </span>
            {Array.from({ length: maxSection + 1 }, (_, sec) => {
              const count = lookup.get(`${sec}:${iter + 1}`) ?? 0
              const intensity = count / maxCount
              const bg = count === 0
                ? '#1A1D27'
                : `rgba(124, 140, 255, ${0.15 + intensity * 0.85})`
              return (
                <div
                  key={sec}
                  title={`§${sec + 1} — iter ${iter + 1}: ${count} run`}
                  style={{
                    width: CELL_W,
                    height: CELL_H,
                    background: bg,
                    border: '1px solid #2A2D3A',
                    borderRadius: 2,
                    flexShrink: 0,
                  }}
                />
              )
            })}
          </div>
        ))}
        {/* X axis labels */}
        <div style={{ display: 'flex', gap: 4, marginLeft: 20 }}>
          {Array.from({ length: maxSection + 1 }, (_, sec) => (
            <div key={sec} style={{ width: CELL_W, textAlign: 'center', fontSize: 9, color: '#50536A', fontFamily: 'monospace', flexShrink: 0 }}>
              §{sec + 1}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
