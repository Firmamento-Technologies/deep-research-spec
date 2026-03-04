// SourceCard — riga singola nella lista fonti di uno spazio.
//
// Mostra:
//   icona tipo     — fileIcon() da types/space
//   nome           — troncato se troppo lungo
//   info secondaria — MIME label · dimensione · N chunk
//   status badge   — uploading / indexing (spinner) / ready / error
//   progress bar   — durante upload XHR (0-100%)
//   tasto delete   — visibile su hover

import { useEffect, useRef }   from 'react'
import { useSpaceStore }       from '../../store/useSpaceStore'
import {
  fileIcon, formatSize, MIME_LABELS,
  type Source,
} from '../../types/space'

const STATUS_STYLES: Record<Source['status'], string> = {
  uploading: 'text-drs-yellow  bg-drs-s3',
  indexing:  'text-drs-accent  bg-drs-s3',
  ready:     'text-drs-green   bg-drs-s3',
  error:     'text-drs-red     bg-drs-s3',
}

const STATUS_LABEL: Record<Source['status'], string> = {
  uploading: 'Upload\u2026',
  indexing:  'Indicizzazione\u2026',
  ready:     'Pronta',
  error:     'Errore',
}

interface Props {
  source:  Source
  spaceId: string | null
}

export function SourceCard({ source, spaceId }: Props) {
  const { deleteSource, watchSource } = useSpaceStore()

  // Apri watch SSE se la fonte è ancora in indicizzazione al mount
  // (es. refresh pagina con fonte in volo)
  const watchedRef = useRef(false)
  useEffect(() => {
    if (!watchedRef.current && (source.status === 'indexing' || source.status === 'uploading')) {
      watchedRef.current = true
      const cleanup = watchSource(spaceId, source.id)
      return cleanup
    }
  }, [source.status, source.id, spaceId, watchSource])

  const isActive   = source.status === 'uploading' || source.status === 'indexing'
  const mimeLabel  = source.mimeType ? (MIME_LABELS[source.mimeType] ?? source.mimeType) : ''
  const sizeLabel  = source.size !== null ? formatSize(source.size) : ''
  const chunkLabel = source.status === 'ready' && source.chunkCount > 0
    ? `${source.chunkCount} chunk`
    : ''

  const meta = [mimeLabel, sizeLabel, chunkLabel].filter(Boolean).join(' \u00B7 ')

  return (
    <div
      className="group flex items-start gap-3 bg-drs-s2 border border-drs-border
        rounded-input px-3 py-2.5 hover:border-drs-border-bright transition-colors"
    >
      {/* Icona */}
      <span className="text-base leading-none mt-0.5 shrink-0" aria-hidden>
        {fileIcon(source)}
      </span>

      {/* Testo */}
      <div className="flex-1 min-w-0">
        {/* Nome + URL */}
        {source.type === 'url' && source.url ? (
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-drs-text hover:text-drs-accent truncate block
              transition-colors"
            title={source.url}
          >
            {source.name}
          </a>
        ) : (
          <p className="text-xs text-drs-text truncate" title={source.name}>
            {source.name}
          </p>
        )}

        {/* Meta */}
        {meta && (
          <p className="text-xs text-drs-faint mt-0.5 truncate">{meta}</p>
        )}

        {/* Progress bar (upload XHR) */}
        {source.status === 'uploading' && source.uploadProgress !== undefined && (
          <div className="mt-1.5 h-0.5 bg-drs-s3 rounded-full overflow-hidden">
            <div
              className="h-full bg-drs-accent transition-all duration-200 rounded-full"
              style={{ width: `${source.uploadProgress}%` }}
            />
          </div>
        )}

        {/* Messaggio errore */}
        {source.status === 'error' && source.error && (
          <p className="text-xs text-drs-red mt-1 truncate" title={source.error}>
            {source.error}
          </p>
        )}
      </div>

      {/* Status badge + delete */}
      <div className="flex items-center gap-2 shrink-0">
        <span
          className={`inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full
            font-medium ${ STATUS_STYLES[source.status] }`}
        >
          {isActive && (
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
          )}
          {STATUS_LABEL[source.status]}
        </span>

        <button
          onClick={() => void deleteSource(spaceId, source.id)}
          aria-label={`Rimuovi fonte ${source.name}`}
          title="Rimuovi fonte"
          className="opacity-0 group-hover:opacity-100 focus:opacity-100
            text-drs-faint hover:text-drs-red transition-all text-sm leading-none"
        >
          \u00D7
        </button>
      </div>
    </div>
  )
}
