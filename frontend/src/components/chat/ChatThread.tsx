// ChatThread — the scrollable conversation view.
// Mounted in MainArea's HomeView for IDLE / CONVERSING / REVIEWING states.
// Auto-scrolls to bottom on new messages and typing indicator.
// Spec: UI_BUILD_PLAN.md Section 6.

import { useEffect, useRef } from 'react'
import { useConversationStore } from '../../store/useConversationStore'
import { MessageBubble } from './MessageBubble'
import { TypingIndicator } from './TypingIndicator'

export function ChatThread() {
  const messages  = useConversationStore((s) => s.messages)
  const isTyping  = useConversationStore((s) => s.isTyping)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Smooth scroll to bottom on new content
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, isTyping])

  return (
    <div className="w-full h-full overflow-y-auto flex flex-col" role="log" aria-live="polite" aria-label="Chat conversation">
      {/* Content — centred column, max-width 720px */}
      <div className="flex-1 flex flex-col gap-3 max-w-[720px] mx-auto w-full px-4 pt-6 pb-4">

        {/* Empty state */}
        {messages.length === 0 && !isTyping && (
          <div className="flex-1 flex flex-col items-center justify-center select-none py-24">
            <p className="text-drs-accent font-mono text-4xl mb-4">◈</p>
            <p className="text-drs-text font-semibold text-lg mb-1">Deep Research System</p>
            <p className="text-drs-muted text-sm">Cosa vuoi esplorare oggi?</p>
          </div>
        )}

        {/* Message bubbles */}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* Typing indicator — aligned left like companion messages */}
        {isTyping && <TypingIndicator />}

        {/* Invisible scroll anchor */}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
