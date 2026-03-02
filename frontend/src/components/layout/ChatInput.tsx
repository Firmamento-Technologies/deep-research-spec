// ChatInput — ALWAYS MOUNTED AND ALWAYS VISIBLE in every app state.
// Fixed bottom, h-20. Never unmounted. Survives route changes and modal overlays.
// Spec: UI_BUILD_PLAN.md Section 2, note 3.
//
// Layout:
//   [Model selector] | [textarea auto-resize] | [↑ send]
//
// Enter = send  /  Shift+Enter = newline

import { useState, useRef, useCallback, type KeyboardEvent, type ChangeEvent } from 'react'
import { useConversationStore } from '../../store/useConversationStore'
import { useAppStore } from '../../store/useAppStore'

export function ChatInput() {
  const [text, setText]           = useState('')
  const textareaRef               = useRef<HTMLTextAreaElement>(null)
  const sendMessage               = useConversationStore((s) => s.sendMessage)
  const appState                  = useAppStore((s) => s.state)
  const setState                  = useAppStore((s) => s.setState)

  const handleSend = useCallback(async () => {
    const trimmed = text.trim()
    if (!trimmed) return
    setText('')
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
    // State transitions on first message
    if (appState === 'IDLE')      setState('CONVERSING')
    if (appState === 'REVIEWING') setState('CONVERSING')
    await sendMessage(trimmed)
  }, [text, appState, setState, sendMessage])

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSend()
    }
  }

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value)
    // Auto-resize up to 200px
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }

  const canSend = text.trim().length > 0

  return (
    <div
      className={
        'fixed bottom-0 left-0 right-0 z-40 h-20 ' +
        'bg-drs-s1 border-t border-drs-border ' +
        'flex items-center px-4 gap-3'
      }
    >
      {/* Left: model selector — full dropdown wired in STEP 5 */}
      <button
        className={
          'shrink-0 px-2.5 py-1 rounded ' +
          'bg-drs-s2 border border-drs-border ' +
          'text-drs-muted text-xs font-mono ' +
          'hover:border-drs-border-bright transition-colors whitespace-nowrap'
        }
      >
        Sonnet 4.6 ▾
      </button>

      {/* Center: textarea */}
      <textarea
        ref={textareaRef}
        value={text}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder="Scrivi a DRS..."
        rows={1}
        className={
          'flex-1 bg-drs-s2 border border-drs-border rounded-[4px] ' +
          'px-3 py-2.5 text-sm text-drs-text placeholder:text-drs-faint ' +
          'resize-none outline-none focus:border-drs-border-bright ' +
          'transition-colors min-h-[40px] max-h-[200px] font-sans leading-snug'
        }
      />

      {/* Right: send button */}
      <button
        onClick={() => void handleSend()}
        disabled={!canSend}
        aria-label="Invia"
        className={
          'shrink-0 w-9 h-9 rounded flex items-center justify-center ' +
          'font-mono text-base transition-opacity ' +
          (canSend
            ? 'bg-drs-accent text-white hover:opacity-90 cursor-pointer'
            : 'bg-drs-s3 text-drs-faint cursor-not-allowed opacity-40')
        }
      >
        ↑
      </button>
    </div>
  )
}
