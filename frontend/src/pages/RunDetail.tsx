import { useState, useEffect, type FC } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Card } from '../components/ui/Card'
import { api } from '../lib/api'

interface RunInfo {
  doc_id: string
  topic: string
  status: string
  quality_preset: string
  total_cost: number
  total_words: number
  created_at: string | null
  completed_at: string | null
}

interface SectionData {
  idx: number
  title: string
  content: string
  status: string
}

export const RunDetail: FC = () => {
  const { docId } = useParams<{ docId: string }>()
  const [run, setRun] = useState<RunInfo | null>(null)
  const [sections, setSections] = useState<SectionData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!docId) return
    async function fetchData() {
      try {
        const [runRes, secRes] = await Promise.all([
          api.get(`/api/runs/${docId}`),
          api.get(`/api/runs/${docId}/sections`),
        ])
        setRun(runRes.data)
        setSections(secRes.data)
      } catch (e: any) {
        setError(e?.message || 'Errore nel caricamento')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [docId])

  if (loading) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <p className="text-drs-faint text-sm font-mono">Caricamento...</p>
      </div>
    )
  }

  if (error || !run) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <p className="text-drs-red text-sm">{error || 'Run non trovato'}</p>
        <Link to="/dashboard" className="text-drs-accent text-sm mt-2 inline-block">
          Torna alla Dashboard
        </Link>
      </div>
    )
  }

  const statusColors: Record<string, string> = {
    completed: 'bg-drs-green/20 text-drs-green',
    running: 'bg-drs-accent/20 text-drs-accent',
    failed: 'bg-red-500/20 text-red-400',
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <Link to="/dashboard" className="text-drs-muted text-xs hover:text-drs-text transition-colors">
            &larr; Dashboard
          </Link>
          <h1 className="text-2xl font-bold text-drs-text mt-1 break-words">{run.topic}</h1>
          <div className="flex items-center gap-3 mt-2 flex-wrap">
            <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${statusColors[run.status] || 'bg-drs-s3 text-drs-muted'}`}>
              {run.status}
            </span>
            <span className="text-xs text-drs-faint">{run.quality_preset}</span>
            <span className="text-xs text-drs-faint">${run.total_cost?.toFixed(2) ?? '0.00'}</span>
            {run.total_words > 0 && (
              <span className="text-xs text-drs-faint">{run.total_words.toLocaleString()} parole</span>
            )}
            {run.created_at && (
              <span className="text-xs text-drs-faint">
                {new Date(run.created_at).toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' })}
              </span>
            )}
          </div>
        </div>

        {/* Download buttons */}
        <div className="flex gap-2 shrink-0">
          <a
            href={`/api/runs/${docId}/export/markdown`}
            className="rounded-lg border border-drs-border px-3 py-2 text-xs text-drs-text hover:bg-drs-s2 transition"
          >
            Markdown
          </a>
          <a
            href={`/api/runs/${docId}/export/docx`}
            className="rounded-lg border border-drs-border px-3 py-2 text-xs text-drs-text hover:bg-drs-s2 transition"
          >
            DOCX
          </a>
          <a
            href={`/api/runs/${docId}/export/pdf`}
            className="rounded-lg bg-drs-accent px-3 py-2 text-xs text-white hover:brightness-110 transition"
          >
            PDF
          </a>
        </div>
      </div>

      {/* Document content */}
      {sections.length === 0 ? (
        <Card>
          <p className="text-drs-muted text-sm text-center py-8">
            {run.status === 'completed'
              ? 'Nessuna sezione disponibile per questo documento.'
              : 'Il documento non e ancora stato completato.'}
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {sections.map((section) => (
            <Card key={section.idx}>
              <h2 className="text-lg font-semibold text-drs-text mb-3">
                {section.idx + 1}. {section.title}
              </h2>
              <div
                className="prose prose-invert prose-sm max-w-none text-drs-muted leading-relaxed whitespace-pre-wrap"
              >
                {section.content || <span className="text-drs-faint italic">Contenuto non disponibile</span>}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
