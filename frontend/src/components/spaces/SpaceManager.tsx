// SpaceManager — vista principale del sistema Spazi.
//
// Layout:
//   colonna sinistra  (320px) — lista spazi + pulsante “Nuovo spazio”
//   colonna destra              — pannello dettaglio spazio selezionato:
//                                   header (nome + desc + edit)
//                                   SourceUploader (drop zone + URL)
//                                   lista SourceCard
//
// Esposto come <SpaceManager /> in AppShell accanto a “Impostazioni”.

import { useEffect, useState, useCallback, type ChangeEvent } from 'react'
import { useSpaceStore }  from '../../store/useSpaceStore'
import { SpaceCard }      from './SpaceCard'
import { SourceUploader } from './SourceUploader'
import { SourceCard }     from './SourceCard'

const INPUT =
  'w-full bg-drs-s2 border border-drs-border rounded-input ' +
  'px-3 py-2 text-sm text-drs-text placeholder:text-drs-faint ' +
  'outline-none focus:border-drs-border-bright transition-colors'

const LABEL = 'block text-xs font-medium text-drs-muted mb-1.5'

export function SpaceManager() {
  const {
    spaces, sources, selectedSpaceId, loadingSpaces, error,
    fetchSpaces, createSpace, updateSpace, deleteSpace,
    fetchSources, selectSpace,
  } = useSpaceStore()

  // form “Nuovo spazio”
  const [creating,    setCreating]    = useState(false)
  const [newName,     setNewName]     = useState('')
  const [newDesc,     setNewDesc]     = useState('')
  const [savingNew,   setSavingNew]   = useState(false)

  // edit inline del nome spazio
  const [editingId,   setEditingId]   = useState<string | null>(null)
  const [editName,    setEditName]    = useState('')
  const [savingEdit,  setSavingEdit]  = useState(false)

  // conferma delete
  const [deleteId,    setDeleteId]    = useState<string | null>(null)

  const selectedSpace = spaces.find((s) => s.id === selectedSpaceId) ?? null
  const selectedSources = selectedSpaceId
    ? (sources[selectedSpaceId] ?? [])
    : []

  // Carica spazi al mount
  useEffect(() => { void fetchSpaces() }, [fetchSpaces])

  // Carica fonti quando cambia lo spazio selezionato
  useEffect(() => {
    if (selectedSpaceId) void fetchSources(selectedSpaceId)
  }, [selectedSpaceId, fetchSources])

  // ─ Crea spazio
  const handleCreate = useCallback(async () => {
    if (!newName.trim()) return
    setSavingNew(true)
    try {
      const sp = await createSpace(newName.trim(), newDesc.trim())
      setCreating(false); setNewName(''); setNewDesc('')
      selectSpace(sp.id)
    } finally {
      setSavingNew(false)
    }
  }, [newName, newDesc, createSpace, selectSpace])

  // ─ Salva modifica nome
  const handleSaveEdit = useCallback(async () => {
    if (!editingId || !editName.trim()) return
    setSavingEdit(true)
    try {
      await updateSpace(editingId, editName.trim())
      setEditingId(null)
    } finally {
      setSavingEdit(false)
    }
  }, [editingId, editName, updateSpace])

  // ─ Delete spazio
  const handleDelete = useCallback(async (id: string) => {
    await deleteSpace(id)
    setDeleteId(null)
  }, [deleteSpace])

  return (
    <div className="flex h-full overflow-hidden">

      {/* ── Sidebar: lista spazi ────────────────────────────────────────────── */}
      <div className="w-80 shrink-0 border-r border-drs-border flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-drs-border shrink-0">
          <span className="text-xs font-semibold text-drs-text">Knowledge Spaces</span>
          <button
            onClick={() => setCreating((v) => !v)}
            title="Nuovo spazio"
            className="text-drs-accent hover:opacity-75 transition-opacity text-base leading-none"
          >+</button>
        </div>

        {/* Form nuovo spazio */}
        {creating && (
          <div className="px-4 py-3 border-b border-drs-border space-y-2 shrink-0">
            <input
              autoFocus
              value={newName}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setNewName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') void handleCreate() }}
              placeholder="Nome spazio"
              className={INPUT + ' text-xs'}
            />
            <input
              value={newDesc}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setNewDesc(e.target.value)}
              placeholder="Descrizione (opzionale)"
              className={INPUT + ' text-xs'}
            />
            <div className="flex gap-2">
              <button
                onClick={() => void handleCreate()}
                disabled={!newName.trim() || savingNew}
                className="flex-1 py-1.5 text-xs bg-drs-accent text-white rounded-input disabled:opacity-40 hover:opacity-90 transition-opacity"
              >{savingNew ? 'Salvataggio…' : 'Crea'}</button>
              <button
                onClick={() => { setCreating(false); setNewName(''); setNewDesc('') }}
                className="px-3 py-1.5 text-xs text-drs-muted border border-drs-border rounded-input hover:border-drs-border-bright transition-colors"
              >Annulla</button>
            </div>
          </div>
        )}

        {/* Lista */}
        <div className="flex-1 overflow-y-auto py-1">
          {loadingSpaces && (
            <p className="text-xs text-drs-faint px-4 py-3">Caricamento…</p>
          )}
          {!loadingSpaces && spaces.length === 0 && (
            <div className="px-4 py-6 text-center">
              <p className="text-xs text-drs-faint">Nessuno spazio creato.</p>
              <p className="text-xs text-drs-faint mt-1">Clicca “+” per iniziare.</p>
            </div>
          )}
          {spaces.map((sp) => (
            <SpaceCard
              key={sp.id}
              space={sp}
              selected={sp.id === selectedSpaceId}
              onClick={() => selectSpace(sp.id)}
              onDelete={() => setDeleteId(sp.id)}
            />
          ))}
        </div>

        {error && (
          <div className="px-4 py-2 text-xs text-drs-red border-t border-drs-border shrink-0">
            {error}
          </div>
        )}
      </div>

      {/* ── Main: dettaglio spazio ─────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {!selectedSpace ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <p className="text-2xl mb-3">\uD83D\uDDC2\uFE0F</p>
              <p className="text-sm text-drs-muted">Seleziona uno spazio per gestire le fonti</p>
              <p className="text-xs text-drs-faint mt-1">oppure crea un nuovo Knowledge Space</p>
            </div>
          </div>
        ) : (
          <>
            {/* Header spazio */}
            <div className="px-5 py-3 border-b border-drs-border shrink-0 flex items-center gap-3">
              {editingId === selectedSpace.id ? (
                <div className="flex items-center gap-2 flex-1">
                  <input
                    autoFocus
                    value={editName}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setEditName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') void handleSaveEdit()
                      if (e.key === 'Escape') setEditingId(null)
                    }}
                    className={INPUT + ' text-xs max-w-xs'}
                  />
                  <button
                    onClick={() => void handleSaveEdit()}
                    disabled={savingEdit}
                    className="text-xs text-drs-accent hover:opacity-75 transition-opacity"
                  >{savingEdit ? '…' : '\u2713'}</button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="text-xs text-drs-faint hover:text-drs-muted transition-colors"
                  >\u00D7</button>
                </div>
              ) : (
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <h2 className="text-sm font-semibold text-drs-text truncate">{selectedSpace.name}</h2>
                  {selectedSpace.description && (
                    <span className="text-xs text-drs-faint truncate">— {selectedSpace.description}</span>
                  )}
                  <button
                    onClick={() => { setEditingId(selectedSpace.id); setEditName(selectedSpace.name) }}
                    title="Rinomina"
                    className="text-drs-faint hover:text-drs-muted text-xs transition-colors shrink-0"
                  >\u270F\uFE0F</button>
                </div>
              )}
              <span className="text-xs text-drs-faint shrink-0">
                {selectedSources.length} {selectedSources.length === 1 ? 'fonte' : 'fonti'}
              </span>
            </div>

            {/* Uploader */}
            <div className="px-5 pt-4 shrink-0">
              <SourceUploader spaceId={selectedSpace.id} />
            </div>

            {/* Lista fonti */}
            <div className="flex-1 overflow-y-auto px-5 pt-3 pb-4 space-y-2">
              {selectedSources.length === 0 && (
                <p className="text-xs text-drs-faint py-4 text-center">
                  Nessuna fonte. Carica un file o aggiungi un URL.
                </p>
              )}
              {selectedSources.map((src) => (
                <SourceCard key={src.id} source={src} spaceId={selectedSpace.id} />
              ))}
            </div>
          </>
        )}
      </div>

      {/* ── Modale conferma delete ── */}
      {deleteId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(10,11,15,0.80)' }}
          onClick={() => setDeleteId(null)}
        >
          <div
            className="bg-drs-s1 border border-drs-border rounded-card p-5 w-80 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-sm font-semibold text-drs-text mb-1">Elimina spazio</p>
            <p className="text-xs text-drs-muted mb-4">
              Tutti i file e i vettori verranno eliminati permanentemente. Questa azione non è reversibile.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setDeleteId(null)}
                className="px-4 py-1.5 text-xs text-drs-muted border border-drs-border rounded-input hover:border-drs-border-bright transition-colors"
              >Annulla</button>
              <button
                onClick={() => void handleDelete(deleteId)}
                className="px-4 py-1.5 text-xs text-white bg-drs-red rounded-input hover:opacity-90 transition-opacity"
              >Elimina</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
