// MessageBubble — renders a single conversation turn.
// User:     right-aligned, bg-drs-accent, white text, rounded-br-[4px]
// Companion: left-aligned, bg-drs-s1 border, text-drs-text, rounded-bl-[4px]
// Companion messages support inline **bold** and `code` formatting.
// Chips (if present) are rendered below the companion bubble.
// Spec: UI_BUILD_PLAN.md Section 6.

import type { Message } from '../../store/useConversationStore'
import { SuggestionChips } from './SuggestionChips'

interface MessageBubbleProps {
  message: Message
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`flex flex-col gap-1.5 max-w-[75%] ${isUser ? 'items-end' : 'items-start'}`}
      >
        {/* Bubble body */}
        <div
          className={
            'px-4 py-2.5 text-sm leading-relaxed ' +
            (isUser
              ? 'bg-drs-accent text-white rounded-[12px] rounded-br-[4px]'
              : 'bg-drs-s1 border border-drs-border text-drs-text rounded-[12px] rounded-bl-[4px]')
          }
        >
          {isUser ? (
            <span className="whitespace-pre-wrap">{message.content}</span>
          ) : (
            <RichContent content={message.content} />
          )}
        </div>

        {/* Timestamp */}
        <span className={`text-[10px] text-drs-faint px-1 ${isUser ? 'text-right' : 'text-left'}`}>
          {message.timestamp.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })}
        </span>

        {/* Suggestion chips — only for companion messages */}
        {!isUser && message.chips && message.chips.length > 0 && (
          <SuggestionChips chips={message.chips} />
        )}
      </div>
    </div>
  )
}

/**
 * Renders companion text with minimal inline markdown:
 * **bold** and `inline code`.
 * Does not use a full markdown library to keep bundle size small.
 */
function RichContent({ content }: { content: string }) {
  const parts = content.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)

  return (
    <span className="whitespace-pre-wrap">
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return (
            <strong key={i} className="font-semibold">
              {part.slice(2, -2)}
            </strong>
          )
        }
        if (part.startsWith('`') && part.endsWith('`')) {
          return (
            <code
              key={i}
              className="bg-drs-s2 rounded px-1 py-0.5 text-xs font-mono text-drs-accent"
            >
              {part.slice(1, -1)}
            </code>
          )
        }
        return <span key={i}>{part}</span>
      })}
    </span>
  )
}
