// ChatInput — SEMPRE MONTATO E SEMPRE VISIBILE in ogni stato dell'app.
// Fixed bottom, h-20. Non viene mai smontato.
//
// Layout:
//   [+ Nuova ricerca] | [textarea auto-resize] | [↑ invia]
//
// Il pulsante "Nuova ricerca" apre il RunWizard (non visibile durante PROCESSING).
// Enter = invia  /  Shift+Enter = nuova riga

import { useState, useRef, useCallback, type KeyboardEvent, type ChangeEvent } from 'react'
import { useConversationStore } from '../../store/useConversationStore'
import { useAppStore } from '../../store/useAppStore'

export function ChatInput() {
  const [text, setText]     = useState('')
  const textareaRef         = useRef<HTMLTextAreaElement>(null)
  const sendMessage         = useConversationStore((s) => s.sendMessage)
  const appState            = useAppStore((s) => s.state)
  const setState            = useAppStore((s) => s.setState)
  const openWizard          = useAppStore((s) => s.openWizard)

  const handleSend = useCallback(async () => {
    const trimmed = text.trim()
    if (!trimmed) return
    setText('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
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
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }

  const canSend      = text.trim().length > 0
  // Mostra "Nuova ricerca" solo quando non c'è un run attivo
  const showWizardBtn = appState === 'IDLE' || appState === 'CONVERSING' || appState === 'REVIEWING'

  return (
    <div
      className={
        'fixed bottom-0 left-0 right-0 z-40 h-20 ' +
        'bg-drs-s1 border-t border-drs-border ' +
        'flex items-center px-4 gap-3'
      }
    >
      {/* Pulsante Nuova ricerca — apre RunWizard */}
      {showWizardBtn && (
        <button
          onClick={openWizard}
          title="Avvia una nuova ricerca DRS"
          className={
            'shrink-0 px-2.5 py-1 rounded ' +
            'bg-drs-s2 border border-drs-border ' +
            'text-drs-muted text-xs font-mono ' +
            'hover:border-drs-accent hover:text-drs-accent transition-colors whitespace-nowrap'
          }
        >
          + ricerca
        </button>
      )}

      {/* Indicatore run attivo (visibile durante PROCESSING) */}
      {!showWizardBtn && (
        <div
          className={
            'shrink-0 px-2.5 py-1 rounded ' +
            'bg-drs-s2 border border-drs-border ' +
            'text-drs-accent text-xs font-mono ' +
            'flex items-center gap-1.5'
          }
        >
          <span className="w-1.5 h-1.5 rounded-full bg-drs-accent animate-dot-pulse" />
          {appState === 'AWAITING_HUMAN' ? 'in attesa' : 'in esecuzione'}
        </div>
      )}

      {/* Textarea */}
      <textarea
        ref={textareaRef}
        value={text}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={appState === 'PROCESSING' ? 'Chiedi al Companion sul run in corso…' : 'Scrivi a DRS…'}
        rows={1}
        className={
          'flex-1 bg-drs-s2 border border-drs-border rounded-input ' +
          'px-3 py-2.5 text-sm text-drs-text placeholder:text-drs-faint ' +
          'resize-none outline-none focus:border-drs-border-bright ' +
          'transition-colors min-h-[40px] max-h-[200px] font-sans leading-snug'
        }
      />

      {/* Pulsante invia */}
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
