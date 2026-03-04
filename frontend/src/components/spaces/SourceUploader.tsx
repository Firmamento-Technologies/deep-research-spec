// SourceUploader — drop zone per file + input URL.
//
// Comportamento:
//   1. Drag-and-drop su tutta la zona: carica il file
//   2. Click “Scegli file”: file picker
//   3. Input URL + “Aggiungi”: aggiunge sorgente web
//
// Dopo ogni upload avvia watchSource() per aggiornare lo status in real-time.
// Tipi accettati: PDF, DOCX, PPTX, MD, TXT, RST, RTF, JPEG, PNG, WebP, TIFF.

import {
  useState, useRef, useCallback,
  type DragEvent, type ChangeEvent,
} from 'react'
import { useSpaceStore }  from '../../store/useSpaceStore'

const ACCEPT = [
  '.pdf',
  '.docx','.pptx',
  '.md','.txt','.rst','.rtf',
  '.jpg','.jpeg','.png','.webp','.gif','.bmp','.tiff',
].join(',')

interface Props {
  spaceId: string | null  // null = ad-hoc
}

export function SourceUploader({ spaceId }: Props) {
  const { uploadFile, addUrl, watchSource } = useSpaceStore()

  const [dragging,  setDragging]  = useState(false)
  const [url,       setUrl]       = useState('')
  const [urlError,  setUrlError]  = useState<string | null>(null)
  const [addingUrl, setAddingUrl] = useState(false)

  const inputRef = useRef<HTMLInputElement>(null)

  // ─ Upload file (da drag o file picker)
  const processFile = useCallback(async (file: File) => {
    try {
      const src = await uploadFile(spaceId, file)
      // Apri SSE watch; il cleanup avviene internamente quando status = ready|error
      watchSource(spaceId, src.id)
    } catch {
      // L'errore è già salvato nel record source nello store
    }
  }, [spaceId, uploadFile, watchSource])

  const handleFiles = useCallback((files: FileList | null) => {
    if (!files) return
    Array.from(files).forEach((f) => void processFile(f))
  }, [processFile])

  // ─ Drag-and-drop handlers
  const onDragOver  = useCallback((e: DragEvent) => { e.preventDefault(); setDragging(true) }, [])
  const onDragLeave = useCallback(() => setDragging(false), [])
  const onDrop      = useCallback((e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    handleFiles(e.dataTransfer.files)
  }, [handleFiles])

  // ─ File picker
  const onPickChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => handleFiles(e.target.files),
    [handleFiles]
  )

  // ─ Aggiungi URL
  const handleAddUrl = useCallback(async () => {
    const trimmed = url.trim()
    if (!trimmed) return
    if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
      setUrlError('URL non valido. Deve iniziare con http:// o https://')
      return
    }
    setUrlError(null)
    setAddingUrl(true)
    try {
      const src = await addUrl(spaceId, trimmed)
      watchSource(spaceId, src.id)
      setUrl('')
    } catch (e) {
      setUrlError(e instanceof Error ? e.message : 'Errore aggiunta URL')
    } finally {
      setAddingUrl(false)
    }
  }, [url, spaceId, addUrl, watchSource])

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`relative flex flex-col items-center justify-center gap-1.5
          border-2 border-dashed rounded-card py-5 cursor-pointer
          transition-colors select-none
          ${
            dragging
              ? 'border-drs-accent bg-drs-s3'
              : 'border-drs-border bg-drs-s2 hover:border-drs-border-bright hover:bg-drs-s3'
          }`}
      >
        <span className="text-xl">{dragging ? '\uD83D\uDCC2' : '\uD83D\uDCC4'}</span>
        <p className="text-xs text-drs-muted">
          {dragging
            ? 'Rilascia per caricare'
            : <><span className="text-drs-accent">Scegli file</span> o trascina qui</>}
        </p>
        <p className="text-xs text-drs-faint">
          PDF · DOCX · PPTX · MD · TXT · Immagini &mdash; max 50 MB
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          multiple
          onChange={onPickChange}
          className="sr-only"
          aria-label="Carica file"
        />
      </div>

      {/* URL input */}
      <div className="flex gap-2">
        <input
          type="url"
          value={url}
          onChange={(e: ChangeEvent<HTMLInputElement>) => { setUrl(e.target.value); setUrlError(null) }}
          onKeyDown={(e) => { if (e.key === 'Enter') void handleAddUrl() }}
          placeholder="https://example.com/articolo"
          className="flex-1 bg-drs-s2 border border-drs-border rounded-input
            px-3 py-2 text-xs text-drs-text placeholder:text-drs-faint
            outline-none focus:border-drs-border-bright transition-colors"
        />
        <button
          onClick={() => void handleAddUrl()}
          disabled={addingUrl || !url.trim()}
          className="px-4 py-2 text-xs bg-drs-accent text-white rounded-input
            disabled:opacity-40 hover:opacity-90 transition-opacity shrink-0"
        >
          {addingUrl ? '\u2026' : 'Aggiungi'}
        </button>
      </div>

      {urlError && (
        <p className="text-xs text-drs-red">{urlError}</p>
      )}
    </div>
  )
}
