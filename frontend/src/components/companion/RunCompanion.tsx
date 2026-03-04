// RunCompanion — pannello chat laterale, attivo durante PROCESSING / AWAITING_HUMAN.
// Comunica con POST /api/runs/:docId/companion (context-aware sul run corrente).
// Separato da useConversationStore — messaggi locali, vita uguale al run.
//
// Layout (aperto):
//   CompanionHeader  — titolo, fase corrente, pulsante collapse
//   RunContextPill   — topic truncato + status run
//   MessageList      — scroll oldest-first
//   ChipsBar         — suggerimenti quick-reply dall'ultima risposta
//   InputBar         — textarea + invio (Enter)
//
// Collassato: tab verticale da 28px con testo "COMPANION" ruotato.

import {
  useState, useRef, useEffect, useCallback,
  type KeyboardEvent, type ChangeEvent,
} from 'react'
import { useAppStore } from '../../store/useAppStore'
import { useRunStore } from '../../store/useRunStore'
import { useRunStreamContext } from '../layout/AppShell'
import { api } from '../../lib/api'
import { PHASE_LABEL } from '../../types/stream'
import type { CompanionChatResponse } from '../../types/api'

// ── Tipi locali ───────────────────────────────────────────────────────────
interface CMsg {
  id:     string
  role:   'user' | 'companion'
  text:   string
  ts:     Date
  chips?: { label: string; value: string }[]
}

// ── Chips di apertura ──────────────────────────────────────────────────────
const OPENING_CHIPS: CMsg['chips'] = [
  { label: 'Come sta andando?',   value: 'Come sta andando il run?' },
  { label: 'Ultima sezione',       value: "Dimmi lo stato dell'ultima sezione" },
  { label: 'Budget residuo',       value: 'Quanto budget è rimasto?' },
  { label: 'Annulla',              value: 'Annulla il run corrente' },
]

// ── Mock risposte ──────────────────────────────────────────────────────────
const MOCK_POOL = [
  'Il run procede regolarmente. Siamo nella fase di scrittura della sezione 1.',
  'Budget consumato: $0.089 su $50 — rimane l’82%.',
  'La Giuria ha approvato la sezione con CSS C:0.72 S:0.81 F:0.68.',
  'Il Reflector ha emesso 3 istruzioni correttive al Writer (scope PARTIAL).',
  'Agente attivo: writer. Sta generando il draft della sezione corrente.',
]
let mockCursor = 0
async function mockCall(): Promise<CompanionChatResponse> {
  await new Promise((r) => setTimeout(r, 600 + Math.random() * 500))
  const reply = MOCK_POOL[mockCursor % MOCK_POOL.length]
  mockCursor++
  return {
    reply,
    chips: mockCursor % 3 === 0
      ? [{ label: 'Dettagli sezione', value: 'Dettagli della sezione corrente' }]
      : undefined,
  }
}

// ── Timestamp relativo ─────────────────────────────────────────────────────
function relTime(ts: Date): string {
  const s = Math.floor((Date.now() - ts.getTime()) / 1_000)
  if (s < 5)  return 'adesso'
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  return m < 60 ? `${m}m` : `${Math.floor(m / 60)}h`
}

// ── RunCompanion ──────────────────────────────────────────────────────────
export function RunCompanion() {
  const appState        = useAppStore((s) => s.state)
  const activeDocId     = useAppStore((s) => s.activeDocId)
  const companionOpen   = useAppStore((s) => s.companionOpen)
  const toggleCompanion = useAppStore((s) => s.toggleCompanion)
  const setAppState     = useAppStore((s) => s.setState)
  const activeRun       = useRunStore((s) => s.activeRun)
  const { activePhase } = useRunStreamContext()

  const isVisible = appState === 'PROCESSING' || appState === 'AWAITING_HUMAN'

  const [messages,  setMessages]  = useState<CMsg[]>([])
  const [inputText, setInputText] = useState('')
  const [isTyping,  setIsTyping]  = useState(false)
  const [chips,     setChips]     = useState<NonNullable<CMsg['chips']>>(OPENING_CHIPS)

  const listRef     = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll a fondo quando arrivano nuovi messaggi
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages.length, isTyping])

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || !activeDocId || isTyping) return
    const trimmed = text.trim()

    setInputText('')
    setChips([])
    if (textareaRef.current) textareaRef.current.style.height = 'auto'

    const userMsg: CMsg = { id: crypto.randomUUID(), role: 'user', text: trimmed, ts: new Date() }
    setMessages((prev) => [...prev, userMsg])
    setIsTyping(true)

    try {
      const isMock = import.meta.env.VITE_MOCK_COMPANION === 'true'
      let resp: CompanionChatResponse

      if (isMock) {
        resp = await mockCall()
      } else {
        resp = await api.post<CompanionChatResponse>(`/api/runs/${activeDocId}/companion`, {
          message: trimmed,
          conversation_history: messages.slice(-8).map((m) => ({
            id: m.id, role: m.role, content: m.text,
          })),
          current_run_state: activeRun,
        })
      }

      const compMsg: CMsg = {
        id:     crypto.randomUUID(),
        role:   'companion',
        text:   resp.reply,
        ts:     new Date(),
        chips:  resp.chips,
      }
      setMessages((prev) => [...prev, compMsg])
      setChips(resp.chips ?? [])

      // Gestione azioni
      if (resp.action) {
        if (resp.action.type === 'SHOW_SECTION') {
          setAppState('REVIEWING')
        } else if (resp.action.type === 'CANCEL_RUN' && activeDocId) {
          try { await api.delete(`/api/runs/${activeDocId}`) } catch { /* ignora */ }
          setAppState('CONVERSING')
        }
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id:   crypto.randomUUID(),
          role: 'companion' as const,
          text: 'Errore di connessione. Riprova tra qualche istante.',
          ts:   new Date(),
        },
      ])
    } finally {
      setIsTyping(false)
    }
  }, [activeDocId, activeRun, messages, isTyping, setAppState])

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void sendMessage(inputText)
    }
  }

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setInputText(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`
  }

  if (!isVisible) return null

  // ── Collassato: solo tab verticale ─────────────────────────────────
  if (!companionOpen) {
    return (
      <div
        style={{
          width: 28, flexShrink: 0, height: '100%',
          borderLeft: '1px solid #2A2D3A',
          background: '#111318',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        <button
          onClick={toggleCompanion}
          title="Apri Companion"
          style={{
            background: 'transparent', border: 'none', cursor: 'pointer',
            color: '#50536A', padding: '8px 4px',
            display: 'flex', alignItems: 'center',
          }}
        >
          <span
            style={{
              fontSize: 9, fontFamily: 'monospace', letterSpacing: 2,
              writingMode: 'vertical-rl', textOrientation: 'mixed',
              transform: 'rotate(180deg)',
            }}
          >
            COMPANION
          </span>
        </button>
      </div>
    )
  }

  // ── Aperto: pannello completo ───────────────────────────────────────
  return (
    <div
      style={{
        width: 280, flexShrink: 0, height: '100%',
        borderLeft: '1px solid #2A2D3A',
        background: '#111318',
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '10px 12px 8px',
          borderBottom: '1px solid #2A2D3A',
          flexShrink: 0,
          display: 'flex', alignItems: 'flex-start',
          justifyContent: 'space-between', gap: 8,
        }}
      >
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#F0F1F6' }}>Companion</div>
          {activePhase !== 'idle' && activePhase !== 'done' && activePhase !== 'failed' && (
            <div
              style={{
                fontSize: 10, fontFamily: 'monospace',
                color: '#7C8CFF', marginTop: 2,
                display: 'flex', alignItems: 'center', gap: 4,
              }}
            >
              <span
                className="animate-dot-pulse"
                style={{
                  width: 5, height: 5, borderRadius: '50%',
                  background: '#7C8CFF', display: 'inline-block',
                }}
              />
              {PHASE_LABEL[activePhase]}
            </div>
          )}
        </div>
        <button
          onClick={toggleCompanion}
          style={{
            background: 'transparent', border: 'none',
            cursor: 'pointer', color: '#50536A',
            fontSize: 16, lineHeight: 1, paddingTop: 1,
          }}
          title="Chiudi pannello"
        >
          ×
        </button>
      </div>

      {/* Run context pill */}
      {activeRun && (
        <div
          style={{
            padding: '5px 10px',
            borderBottom: '1px solid #2A2D3A',
            flexShrink: 0,
            display: 'flex', alignItems: 'center', gap: 6,
            background: '#0A0B0F',
          }}
        >
          <span style={{ fontSize: 9, fontFamily: 'monospace', color: '#50536A' }}>run</span>
          <span
            style={{
              fontSize: 10, color: '#8B8FA8',
              overflow: 'hidden', textOverflow: 'ellipsis',
              whiteSpace: 'nowrap', flex: 1,
            }}
            title={activeRun.topic}
          >
            {activeRun.topic.length > 38
              ? activeRun.topic.slice(0, 38) + '…'
              : activeRun.topic}
          </span>
          <span
            style={{
              fontSize: 9, fontFamily: 'monospace', flexShrink: 0,
              color: activeRun.status === 'running'             ? '#22C55E'
                   : activeRun.status === 'awaiting_approval'  ? '#EAB308'
                   : '#50536A',
            }}
          >
            {activeRun.status}
          </span>
        </div>
      )}

      {/* Lista messaggi */}
      <div
        ref={listRef}
        style={{
          flex: 1, overflowY: 'auto',
          padding: '10px 10px 4px',
          display: 'flex', flexDirection: 'column', gap: 8,
        }}
      >
        {messages.length === 0 && (
          <div
            style={{
              padding: '14px 4px',
              color: '#50536A', fontSize: 11,
              fontFamily: 'monospace', lineHeight: 1.6,
            }}
          >
            Chiedimi qualcosa sul run in corso.
            Conosco lo stato di ogni agente e posso aiutarti
            a interpretare i risultati.
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
        {isTyping && <TypingIndicator />}
      </div>

      {/* Chips suggeriti */}
      {chips.length > 0 && !isTyping && (
        <div
          style={{
            padding: '5px 10px 6px',
            borderTop: '1px solid #2A2D3A',
            display: 'flex', flexWrap: 'wrap', gap: 4,
            flexShrink: 0,
          }}
        >
          {chips.map((chip) => (
            <ChipButton
              key={chip.value}
              chip={chip}
              onClick={() => void sendMessage(chip.value)}
            />
          ))}
        </div>
      )}

      {/* Input */}
      <div
        style={{
          padding: '8px 10px',
          borderTop: '1px solid #2A2D3A',
          flexShrink: 0,
          display: 'flex', gap: 6, alignItems: 'flex-end',
        }}
      >
        <textarea
          ref={textareaRef}
          value={inputText}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Chiedi al Companion…"
          rows={1}
          style={{
            flex: 1,
            background: '#1A1D27',
            border: '1px solid #2A2D3A',
            borderRadius: 4,
            padding: '6px 8px',
            fontSize: 12,
            color: '#F0F1F6',
            resize: 'none',
            outline: 'none',
            fontFamily: 'Inter var, Inter, sans-serif',
            lineHeight: 1.4,
            minHeight: 32,
            maxHeight: 120,
            transition: 'border-color 0.15s',
          }}
          onFocus={(e) => { e.target.style.borderColor = '#3D4155' }}
          onBlur={(e)  => { e.target.style.borderColor = '#2A2D3A' }}
        />
        <button
          onClick={() => void sendMessage(inputText)}
          disabled={!inputText.trim() || isTyping}
          aria-label="Invia"
          style={{
            width: 30, height: 30,
            borderRadius: 4, border: 'none',
            background: inputText.trim() && !isTyping ? '#7C8CFF' : '#1A1D27',
            color:      inputText.trim() && !isTyping ? '#fff'    : '#50536A',
            cursor:     inputText.trim() && !isTyping ? 'pointer' : 'not-allowed',
            fontSize: 14, flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 0.15s',
          }}
        >
          ↑
        </button>
      </div>
    </div>
  )
}

// ── MessageBubble ──────────────────────────────────────────────────────────
function MessageBubble({ msg }: { msg: CMsg }) {
  const isUser = msg.role === 'user'
  return (
    <div
      style={{
        display: 'flex', flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        gap: 2,
      }}
    >
      <div
        style={{
          maxWidth: '88%',
          padding: '7px 10px',
          borderRadius: isUser
            ? '10px 10px 2px 10px'
            : '10px 10px 10px 2px',
          background: isUser ? '#7C8CFF18' : '#1A1D27',
          border:     `1px solid ${isUser ? '#7C8CFF35' : '#2A2D3A'}`,
          fontSize: 12,
          color: '#F0F1F6',
          lineHeight: 1.5,
          wordBreak: 'break-word',
        }}
      >
        {msg.text}
      </div>
      <span style={{ fontSize: 9, fontFamily: 'monospace', color: '#50536A' }}>
        {relTime(msg.ts)}
      </span>
    </div>
  )
}

// ── TypingIndicator ───────────────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start' }}>
      <div
        style={{
          padding: '8px 14px',
          borderRadius: '10px 10px 10px 2px',
          background: '#1A1D27',
          border: '1px solid #2A2D3A',
          display: 'flex', gap: 5, alignItems: 'center',
        }}
      >
        {[0, 160, 320].map((delay) => (
          <span
            key={delay}
            className="animate-dot-pulse"
            style={{
              width: 4, height: 4,
              borderRadius: '50%',
              background: '#50536A',
              display: 'inline-block',
              animationDelay: `${delay}ms`,
            }}
          />
        ))}
      </div>
    </div>
  )
}

// ── ChipButton ────────────────────────────────────────────────────────────
function ChipButton({
  chip, onClick,
}: {
  chip: { label: string; value: string }
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      style={{
        fontSize: 10,
        padding: '2px 9px',
        borderRadius: 10,
        border: '1px solid #3D4155',
        background: '#1A1D27',
        color: '#8B8FA8',
        cursor: 'pointer',
        whiteSpace: 'nowrap',
        transition: 'border-color 0.15s, color 0.15s',
      }}
      onMouseEnter={(e) => {
        const t = e.currentTarget
        t.style.borderColor = '#7C8CFF'
        t.style.color = '#7C8CFF'
      }}
      onMouseLeave={(e) => {
        const t = e.currentTarget
        t.style.borderColor = '#3D4155'
        t.style.color = '#8B8FA8'
      }}
    >
      {chip.label}
    </button>
  )
}
