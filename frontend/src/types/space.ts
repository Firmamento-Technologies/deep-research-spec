// Space — tipi TypeScript per il sistema Spazi/Fonti.
//
// Separazione deliberata tra:
//   *API shapes*   (snake_case, specchio esatto del JSON restituito da FastAPI)
//   *Frontend types* (camelCase, usati nei componenti e nello store)
//
// Le funzioni mapper (mapSpace / mapSource) fanno l'unica conversione
// necessaria; tutto il resto del frontend usa solo Space e Source.

// ── Status ─────────────────────────────────────────────────────────────────

export type SourceStatus = 'uploading' | 'indexing' | 'ready' | 'error'
export type SourceType   = 'file' | 'url'

// ── API shapes (snake_case) ────────────────────────────────────────────────────────

/** Risposta diretta dall'API (JSON snake_case) */
export interface SpaceAPI {
  id:           string
  name:         string
  description:  string
  created_at:   string
  source_count: number
}

/** Risposta diretta dall'API (JSON snake_case) */
export interface SourceAPI {
  id:           string
  space_id:     string | null
  type:         SourceType
  name:         string
  mime_type:    string | null
  size:         number | null
  url:          string | null
  status:       SourceStatus
  chunk_count:  number
  error:        string | null
  created_at:   string
  content_hash: string | null
}

/** Payload SSE emesso da /stream endpoint durante l'indicizzazione */
export interface SourceStatusEvent {
  id:          string
  status:      SourceStatus
  chunk_count: number
  error:       string | null
  name:        string   // titolo reale (URL sources)
}

// ── Frontend types (camelCase) ─────────────────────────────────────────────────────

export interface Space {
  id:          string
  name:        string
  description: string
  createdAt:   string
  sourceCount: number
}

export interface Source {
  id:          string
  spaceId:     string | null   // null = ad-hoc
  type:        SourceType
  name:        string
  mimeType:    string | null
  size:        number | null   // bytes
  url:         string | null
  status:      SourceStatus
  chunkCount:  number
  error:       string | null
  createdAt:   string
  contentHash: string | null
  /** 0-100, presente solo durante upload XHR */
  uploadProgress?: number
}

// ── Request types (body delle chiamate API) ───────────────────────────────────

export interface CreateSpaceRequest {
  name:        string
  description: string
}

export interface UpdateSpaceRequest {
  name?:        string
  description?: string
}

export interface AddUrlRequest {
  url: string
}

// ── Mapper functions ───────────────────────────────────────────────────────────────

export function mapSpace(a: SpaceAPI): Space {
  return {
    id:          a.id,
    name:        a.name,
    description: a.description,
    createdAt:   a.created_at,
    sourceCount: a.source_count,
  }
}

export function mapSource(a: SourceAPI): Source {
  return {
    id:          a.id,
    spaceId:     a.space_id,
    type:        a.type,
    name:        a.name,
    mimeType:    a.mime_type,
    size:        a.size,
    url:         a.url,
    status:      a.status,
    chunkCount:  a.chunk_count,
    error:       a.error,
    createdAt:   a.created_at,
    contentHash: a.content_hash,
  }
}

// ── UI helpers ──────────────────────────────────────────────────────────────────

/** Etichetta leggibile per tipo MIME (usata in SourceCard). */
export const MIME_LABELS: Record<string, string> = {
  'application/pdf':   'PDF',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'Word',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PowerPoint',
  'application/vnd.ms-powerpoint': 'PowerPoint',
  'application/rtf':   'RTF',
  'text/plain':        'Testo',
  'text/markdown':     'Markdown',
  'text/x-markdown':   'Markdown',
  'text/x-rst':        'reStructuredText',
  'text/html':         'Pagina web',
  'image/jpeg':        'Immagine JPEG',
  'image/png':         'Immagine PNG',
  'image/webp':        'Immagine WebP',
  'image/gif':         'Immagine GIF',
  'image/bmp':         'Immagine BMP',
  'image/tiff':        'Immagine TIFF',
}

/** Icona emoji per tipo sorgente (usata in SourceCard e SourceUploader). */
export function fileIcon(src: Source): string {
  if (src.type === 'url') return '\uD83C\uDF10'  // 🌐
  const m = src.mimeType ?? ''
  if (m === 'application/pdf')      return '\uD83D\uDCC4'  // 📄
  if (m.includes('word'))           return '\uD83D\uDCDD'  // 📝
  if (m.includes('presentation') || m.includes('powerpoint')) return '\uD83D\uDCCA'  // 📊
  if (m.startsWith('image/'))       return '\uD83D\uDDBC\uFE0F'  // 🖼️
  if (m.includes('markdown') || m === 'text/x-markdown') return '\u2318'  // ⌘
  return '\uD83D\uDCC3'  // 📃 default
}

/** Formatta dimensione file in formato leggibile (es. "2.4 MB"). */
export function formatSize(bytes: number | null): string {
  if (bytes === null) return ''
  if (bytes < 1024)         return `${bytes} B`
  if (bytes < 1024 * 1024)  return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** Chiave usata per indicizzare sources nello store (spaceId | '__adhoc__'). */
export const ADHOC_KEY = '__adhoc__'
export function spaceKey(spaceId: string | null): string {
  return spaceId ?? ADHOC_KEY
}
