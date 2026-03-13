// SuggestionChips — horizontal row of quick-reply buttons.
// Clicking a chip sends its 'value' as a new user message.
// Rendered below the last companion message bubble.
// Spec: UI_BUILD_PLAN.md Section 6.

import { useConversationStore } from '../../store/useConversationStore'
import { useAppStore } from '../../store/useAppStore'

interface Chip {
  label: string   // visible button text
  value: string   // text sent when clicked
}

interface SuggestionChipsProps {
  chips: Chip[]
}

export function SuggestionChips({ chips }: SuggestionChipsProps) {
  const sendMessage = useConversationStore((s) => s.sendMessage)
  const appState    = useAppStore((s) => s.state)
  const setState    = useAppStore((s) => s.setState)

  const handleChip = (value: string) => {
    if (appState === 'IDLE') setState('CONVERSING')
    void sendMessage(value)
  }

  return (
    <div className="flex gap-2 flex-wrap">
      {chips.map((chip, i) => (
        <button
          key={i}
          onClick={() => handleChip(chip.value)}
          aria-label={`Suggerimento: ${chip.label}`}
          className={
            'px-3 py-1 rounded-full text-xs ' +
            'border border-drs-accent text-drs-accent ' +
            'hover:bg-drs-accent hover:text-white ' +
            'transition-colors'
          }
        >
          {chip.label}
        </button>
      ))}
    </div>
  )
}
