// TypingIndicator — three pulsing dots shown while isTyping=true.
// Aligned left like companion messages.
// Uses the animate-dot-pulse keyframe from globals.css with staggered delays.

export function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div
        className={
          'flex items-center gap-1.5 px-4 py-3 ' +
          'bg-drs-s1 border border-drs-border ' +
          'rounded-[12px] rounded-bl-[4px]'
        }
      >
        {[0, 150, 300].map((delay, i) => (
          <span
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-drs-accent animate-dot-pulse"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>
    </div>
  )
}
