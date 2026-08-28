import React from 'react'

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
  variant?: 'surface' | 'glass' | 'panel'
}

export function Card({ children, className = '', variant = 'surface', ...rest }: CardProps) {
  const variants: Record<string, string> = {
    surface: 'rounded-xl border border-slate-200 bg-white p-4 shadow-sm',
    glass: 'rounded-[28px] border border-slate-200/10 bg-slate-950/80 p-6 shadow-[0_30px_120px_rgba(2,16,44,0.32)] backdrop-blur-2xl',
    panel: 'rounded-[32px] border border-slate-900/30 bg-slate-950/90 p-7 shadow-[0_28px_90px_rgba(6,19,44,0.28)] backdrop-blur-xl',
  }

  return (
    <div className={[variants[variant] ?? variants.surface, className].join(' ')} {...rest}>
      {children}
    </div>
  )
}

export default Card
