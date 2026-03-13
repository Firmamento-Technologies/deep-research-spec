import React, { useEffect, useState, useCallback } from 'react'
import { api } from '../lib/api'
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
      const params: Record<string, string> = { from, to }
      if (presets.length) params.preset = presets.join(',')
      if (keyword) params.keyword = keyword
      const res = await api.get('/api/analytics', { params })
      setData(res.data)
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
    <div className="p-4 md:p-6 max-w-7xl mx-auto space-y-6">
      <div className="text-[18px] text-drs-text font-bold">Analytics</div>

      {/* Filter bar */}
      <FilterBar
        from={from} to={to} presets={presets} keyword={keyword}
        onFrom={setFrom} onTo={setTo} onTogglePreset={togglePreset}
        onKeyword={setKeyword} onRefresh={fetchData}
      />

      {loading && !data && (
        <div className="text-drs-faint text-[12px] font-mono">Caricamento dati...</div>
      )}

      {error && !data && (
        <div className="flex flex-col items-center justify-center py-16 gap-4">
          <div className="text-drs-faint text-[48px]">&#128202;</div>
          <div className="text-drs-text text-[16px] font-bold">Nessun dato disponibile</div>
          <div className="text-drs-muted text-[13px] font-mono text-center max-w-md">
            Non ci sono ancora dati analytics. I dati appariranno qui dopo aver completato le prime ricerche nel sistema.
          </div>
          <div className="bg-drs-s1 border border-drs-border rounded-card px-4 py-3 mt-2">
            <div className="text-drs-faint text-[11px] font-mono">{error}</div>
          </div>
        </div>
      )}

      {data && (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-[12px]">
            <KpiCard label="Runs completati"    value={data.kpis.total_runs.toString()} />
            <KpiCard label="Costo medio/doc"    value={`$${data.kpis.avg_cost_per_doc.toFixed(2)}`} color="#EAB308" />
            <KpiCard label="Parole totali"      value={data.kpis.total_words.toLocaleString()} color="#7C8CFF" />
            <KpiCard label="CSS medio"          value={data.kpis.avg_css_composite.toFixed(3)} color={data.kpis.avg_css_composite >= 0.70 ? '#22C55E' : '#EF4444'} />
            <KpiCard label="Successo 1ª iter." value={`${(data.kpis.first_iteration_success_rate * 100).toFixed(1)}%`} color="#22C55E" />
          </div>

          {/* 2×2 Chart grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-[16px]">
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
                        <div className="bg-drs-s1 border border-drs-border rounded-[6px] px-[10px] py-[6px] text-[11px]">
                          <div className="text-drs-text">{d?.topic}</div>
                          <div className="text-drs-muted">CSS: {d?.css?.toFixed(3)}  Costo: ${d?.cost?.toFixed(3)}</div>
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
                    formatter={(value) => <span className="text-drs-muted text-[10px]">{value}</span>}
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
  const inputClassName = 'bg-drs-s1 border border-drs-border rounded-input text-drs-text text-[12px] font-mono px-[10px] py-[5px] outline-none'
  return (
    <div className="flex items-center gap-[12px] flex-wrap">
      <span className="text-[11px] text-drs-faint font-mono">DA</span>
      <input type="date" value={from} onChange={e => onFrom(e.target.value)} className={inputClassName} />
      <span className="text-[11px] text-drs-faint font-mono">A</span>
      <input type="date" value={to} onChange={e => onTo(e.target.value)} className={inputClassName} />

      <div className="flex gap-[6px]">
        {PRESET_OPTIONS.map(p => {
          const active = presets.includes(p)
          const color = PRESET_COLORS[p]
          return (
            <button
              key={p}
              onClick={() => onTogglePreset(p)}
              className="px-[10px] py-[4px] rounded-input text-[11px] font-mono cursor-pointer"
              style={{
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
        placeholder="Cerca topic..."
        className={`${inputClassName} w-[180px]`}
      />

      <button
        onClick={onRefresh}
        className="bg-drs-accent border-none rounded-input text-drs-bg text-[12px] font-mono px-[14px] py-[5px] cursor-pointer font-bold"
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
    <div className="bg-drs-s1 border border-drs-border rounded-card px-[16px] py-[14px]">
      <div className="text-[10px] font-mono text-drs-faint tracking-[1px] mb-[6px]">
        {label.toUpperCase()}
      </div>
      <div className="text-[22px] font-mono font-bold leading-none" style={{ color }}>
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
    <div className="bg-drs-s1 border border-drs-border rounded-card px-[16px] py-[14px]">
      <div className="text-[11px] font-mono text-drs-muted mb-[12px] tracking-[0.5px]">
        {title}
      </div>
      {children}
    </div>
  )
}

// ------------------------------------------------------------------ //
// Custom Recharts tooltip
// ------------------------------------------------------------------ //
interface TooltipPayloadEntry {
  name?: string
  value: string | number
  color?: string
}

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: TooltipPayloadEntry[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-drs-s1 border border-drs-border rounded-[6px] px-[10px] py-[6px] text-[11px] font-mono">
      {label && <div className="text-drs-muted mb-[4px]">{label}</div>}
      {payload.map((p: TooltipPayloadEntry, i: number) => (
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
      <div className="h-[220px] flex items-center justify-center">
        <span className="text-[12px] text-drs-faint font-mono">Nessun dato.</span>
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
    <div className="overflow-x-auto h-[220px]">
      <div className="inline-flex flex-col gap-[2px] py-[4px]">
        {/* Y axis label */}
        {Array.from({ length: maxIteration + 1 }, (_, iter) => (
          <div key={iter} className="flex items-center gap-[4px]">
            <span className="text-[9px] font-mono text-drs-faint w-[16px] text-right shrink-0">
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
                  title={`\u00A7${sec + 1} \u2014 iter ${iter + 1}: ${count} run`}
                  className="border border-drs-border rounded-[2px] shrink-0"
                  style={{
                    width: CELL_W,
                    height: CELL_H,
                    background: bg,
                  }}
                />
              )
            })}
          </div>
        ))}
        {/* X axis labels */}
        <div className="flex gap-[4px] ml-[20px]">
          {Array.from({ length: maxSection + 1 }, (_, sec) => (
            <div key={sec} className="text-center text-[9px] text-drs-faint font-mono shrink-0" style={{ width: CELL_W }}>
              {'\u00A7'}{sec + 1}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
