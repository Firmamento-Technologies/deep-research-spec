// SpaceCard — card cliccabile nella sidebar di SpaceManager.
//
// Props:
//   space    — oggetto Space
//   selected — evidenza visiva spazio attivo
//   onClick  — apri dettaglio
//   onDelete — apri modale conferma eliminazione

import type { Space } from '../../types/space'

interface Props {
  space:    Space
  selected: boolean
  onClick:  () => void
  onDelete: () => void
}

export function SpaceCard({ space, selected, onClick, onDelete }: Props) {
  return (
    <div
      onClick={onClick}
      className={`group flex items-start justify-between px-4 py-2.5 cursor-pointer
        border-l-2 transition-colors
        ${
          selected
            ? 'border-l-drs-accent bg-drs-s2 text-drs-text'
            : 'border-l-transparent hover:bg-drs-s2 text-drs-muted hover:text-drs-text'
        }`}
    >
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium truncate">{space.name}</p>
        {space.description && (
          <p className="text-xs text-drs-faint truncate mt-0.5">{space.description}</p>
        )}
      </div>

      <div className="flex items-center gap-2 shrink-0 ml-2">
        {/* Badge conteggio fonti */}
        <span
          className={`text-xs font-mono rounded-full px-1.5 py-0.5 transition-colors ${
            selected
              ? 'bg-drs-s3 text-drs-accent'
              : 'bg-drs-s3 text-drs-faint'
          }`}
        >
          {space.sourceCount}
        </span>

        {/* Delete — visibile solo su hover / focus */}
        <button
          onClick={(e) => { e.stopPropagation(); onDelete() }}
          aria-label={`Elimina spazio ${space.name}`}
          title="Elimina spazio"
          className="opacity-0 group-hover:opacity-100 focus:opacity-100 text-drs-faint
            hover:text-drs-red transition-all text-sm leading-none"
        >
          \u00D7
        </button>
      </div>
    </div>
  )
}
