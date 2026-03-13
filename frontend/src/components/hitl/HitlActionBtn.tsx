import type { ReactNode } from 'react'

interface HitlActionBtnProps {
  children: ReactNode
  onClick: () => void
  disabled?: boolean
  variant: 'primary' | 'ghost'
}

export function HitlActionBtn({ children, onClick, disabled, variant }: HitlActionBtnProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`p-[8px_16px] rounded-[6px] text-[12px] font-mono focus:outline-none focus:ring-2 focus:ring-drs-accent ${
        disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer opacity-100'
      } ${
        variant === 'primary'
          ? 'border-none bg-drs-accent text-drs-bg font-bold'
          : 'border border-drs-border bg-transparent text-drs-muted font-normal'
      }`}
    >
      {children}
    </button>
  )
}
