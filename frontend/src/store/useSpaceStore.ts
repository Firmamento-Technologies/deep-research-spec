// useSpaceStore — Zustand store per il sistema Spazi/Fonti.
//
// State:
//   spaces           — lista spazi persistenti
//   sources          — fonti indicizzate per spaceKey (spaceId | '__adhoc__')
//   selectedSpaceId  — spazio aperto in SpaceManager
//   loadingSpaces    — GET /api/spaces in corso
//   loadingSources   — GET /api/spaces/{id}/sources in corso per spaceKey
//   error            — ultimo errore API (reset a null ad ogni azione)
//
// Upload file:
//   uploadFile usa XHR (non fetch) per il progresso 0-100%.
//   Il progresso è salvato in source.uploadProgress fino a status=ready|error.
//
// SSE status:
//   watchSource apre un EventSource su /stream, aggiorna source.status
//   in real-time e ritorna una funzione di cleanup (da chiamare in useEffect).

import { create }   from 'zustand'
import { api }      from '../lib/api'
import {
  mapSpace, mapSource, spaceKey, ADHOC_KEY,
  type Space, type Source, type SpaceAPI, type SourceAPI,
  type SourceStatusEvent,
} from '../types/space'

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

// ── State & actions interface ──────────────────────────────────────────────────────────

interface SpaceStore {
  // —— State ——
  spaces:          Space[]
  sources:         Record<string, Source[]>   // chiave: spaceKey()
  selectedSpaceId: string | null             // null = schermata lista spazi
  loadingSpaces:   boolean
  loadingSources:  Record<string, boolean>
  error:           string | null

  // —— Navigazione ——
  selectSpace: (id: string | null) => void

  // —— Spaces CRUD ——
  fetchSpaces:  () => Promise<void>
  createSpace:  (name: string, description?: string) => Promise<Space>
  updateSpace:  (id: string, name?: string, description?: string) => Promise<void>
  deleteSpace:  (id: string) => Promise<void>

  // —— Sources CRUD ——
  fetchSources:  (spaceId: string | null) => Promise<void>
  uploadFile:    (spaceId: string | null, file: File) => Promise<Source>
  addUrl:        (spaceId: string | null, url: string) => Promise<Source>
  deleteSource:  (spaceId: string | null, sourceId: string) => Promise<void>

  // —— SSE status watch ——
  /** Apre un EventSource sul /stream endpoint.
   *  Ritorna una funzione di cleanup da usare come return di useEffect. */
  watchSource: (spaceId: string | null, sourceId: string) => () => void

  // —— Internal ——
  _patchSource: (spaceId: string | null, sourceId: string, patch: Partial<Source>) => void
}

// ── XHR upload helper (progress-aware) ─────────────────────────────────────────────

function xhrUpload(
  url: string,
  formData: FormData,
  onProgress: (pct: number) => void,
): Promise<SourceAPI> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE}${url}`)
    xhr.setRequestHeader('Accept', 'application/json')

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
    })

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as SourceAPI)
        } catch {
          reject(new Error('Risposta non valida dal server'))
        }
      } else {
        reject(new Error(`Upload fallito: ${xhr.status} ${xhr.statusText}`))
      }
    })

    xhr.addEventListener('error',  () => reject(new Error('Errore di rete durante upload')))
    xhr.addEventListener('abort',  () => reject(new Error('Upload annullato')))

    xhr.send(formData)
  })
}

// ── Store ───────────────────────────────────────────────────────────────────────────

export const useSpaceStore = create<SpaceStore>((set, get) => ({

  spaces:          [],
  sources:         {},
  selectedSpaceId: null,
  loadingSpaces:   false,
  loadingSources:  {},
  error:           null,

  // ── Navigazione

  selectSpace: (id) => set({ selectedSpaceId: id }),

  // ── Spaces CRUD

  fetchSpaces: async () => {
    set({ loadingSpaces: true, error: null })
    try {
      const data = await api.get<SpaceAPI[]>('/api/spaces')
      set({ spaces: data.map(mapSpace), loadingSpaces: false })
    } catch (e) {
      set({ error: _msg(e), loadingSpaces: false })
    }
  },

  createSpace: async (name, description = '') => {
    set({ error: null })
    const data = await api.post<SpaceAPI>('/api/spaces', { name, description })
    const sp   = mapSpace(data)
    set((s) => ({ spaces: [sp, ...s.spaces] }))
    return sp
  },

  updateSpace: async (id, name, description) => {
    set({ error: null })
    const body: Record<string, string> = {}
    if (name        !== undefined) body.name        = name
    if (description !== undefined) body.description = description
    const data = await api.patch<SpaceAPI>(`/api/spaces/${id}`, body)
    const updated = mapSpace(data)
    set((s) => ({
      spaces: s.spaces.map((sp) => sp.id === id ? updated : sp),
    }))
  },

  deleteSpace: async (id) => {
    set({ error: null })
    await api.delete(`/api/spaces/${id}`)
    set((s) => ({
      spaces:   s.spaces.filter((sp) => sp.id !== id),
      sources:  Object.fromEntries(
        Object.entries(s.sources).filter(([k]) => k !== id)
      ),
      selectedSpaceId: s.selectedSpaceId === id ? null : s.selectedSpaceId,
    }))
  },

  // ── Sources CRUD

  fetchSources: async (spaceId) => {
    const key = spaceKey(spaceId)
    set((s) => ({
      loadingSources: { ...s.loadingSources, [key]: true },
      error: null,
    }))
    try {
      const path = spaceId
        ? `/api/spaces/${spaceId}/sources`
        : `/api/spaces/${ADHOC_KEY}/sources`
      const data = await api.get<SourceAPI[]>(path)
      set((s) => ({
        sources:       { ...s.sources, [key]: data.map(mapSource) },
        loadingSources: { ...s.loadingSources, [key]: false },
      }))
    } catch (e) {
      set((s) => ({
        error:         _msg(e),
        loadingSources: { ...s.loadingSources, [key]: false },
      }))
    }
  },

  uploadFile: async (spaceId, file) => {
    set({ error: null })
    const key     = spaceKey(spaceId)
    const tempId  = crypto.randomUUID()
    const tmpSrc: Source = {
      id:             tempId,
      spaceId,
      type:           'file',
      name:           file.name,
      mimeType:       file.type || null,
      size:           file.size,
      url:            null,
      status:         'uploading',
      chunkCount:     0,
      error:          null,
      createdAt:      new Date().toISOString(),
      contentHash:    null,
      uploadProgress: 0,
    }
    // Aggiungi subito alla lista (feedback immediato in UI)
    set((s) => ({
      sources: {
        ...s.sources,
        [key]: [tmpSrc, ...(s.sources[key] ?? [])],
      },
    }))

    const formData = new FormData()
    formData.append('file', file)
    const uploadUrl = spaceId
      ? `/api/spaces/${spaceId}/sources/file`
      : '/api/sources/adhoc/file'

    try {
      const raw = await xhrUpload(uploadUrl, formData, (pct) => {
        get()._patchSource(spaceId, tempId, { uploadProgress: pct })
      })
      const src = mapSource(raw)
      // Sostituisci il record temporaneo con quello reale
      set((s) => ({
        sources: {
          ...s.sources,
          [key]: (s.sources[key] ?? []).map((s2) =>
            s2.id === tempId ? src : s2
          ),
        },
      }))
      return src
    } catch (e) {
      get()._patchSource(spaceId, tempId, { status: 'error', error: _msg(e) })
      throw e
    }
  },

  addUrl: async (spaceId, url) => {
    set({ error: null })
    const key  = spaceKey(spaceId)
    const path = spaceId
      ? `/api/spaces/${spaceId}/sources/url`
      : '/api/sources/adhoc/url'
    const raw  = await api.post<SourceAPI>(path, { url })
    const src  = mapSource(raw)
    set((s) => ({
      sources: {
        ...s.sources,
        [key]: [src, ...(s.sources[key] ?? [])],
      },
    }))
    return src
  },

  deleteSource: async (spaceId, sourceId) => {
    set({ error: null })
    const key = spaceKey(spaceId)
    if (spaceId) {
      await api.delete(`/api/spaces/${spaceId}/sources/${sourceId}`)
    }
    // Per fonti ad-hoc non c'è un endpoint DELETE standard;
    // le rimuoviamo solo dallo store locale.
    set((s) => ({
      sources: {
        ...s.sources,
        [key]: (s.sources[key] ?? []).filter((s2) => s2.id !== sourceId),
      },
    }))
  },

  // ── SSE status watch

  watchSource: (spaceId, sourceId) => {
    const streamUrl = spaceId
      ? `${BASE}/api/spaces/${spaceId}/sources/${sourceId}/stream`
      : `${BASE}/api/sources/${sourceId}/stream`

    const es = new EventSource(streamUrl)

    es.addEventListener('message', (e: MessageEvent<string>) => {
      try {
        const ev = JSON.parse(e.data) as SourceStatusEvent
        get()._patchSource(spaceId, sourceId, {
          status:     ev.status,
          chunkCount: ev.chunk_count,
          error:      ev.error,
          // Il backend aggiorna il nome per le URL sources (titolo estratto)
          name:       ev.name,
        })
        if (ev.status === 'ready' || ev.status === 'error') {
          es.close()
        }
      } catch {
        // evento malformato, ignora
      }
    })

    es.addEventListener('error', () => es.close())

    return () => es.close()
  },

  // ── Internal patch helper

  _patchSource: (spaceId, sourceId, patch) => {
    const key = spaceKey(spaceId)
    set((s) => ({
      sources: {
        ...s.sources,
        [key]: (s.sources[key] ?? []).map((src) =>
          src.id === sourceId ? { ...src, ...patch } : src
        ),
      },
    }))
  },

}))

// ── Helpers interni ──────────────────────────────────────────────────────────────────

function _msg(e: unknown): string {
  return e instanceof Error ? e.message : 'Errore sconosciuto'
}
