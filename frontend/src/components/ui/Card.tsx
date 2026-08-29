import React from 'react'

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
  variant?: 'surface' | 'glass' | 'panel'
}

export function Card({ children, className = '', variant = 'surface', ...rest }: CardProps) {
  const variants: Record<string, string> = {
    surface: 'rounded-xl border border-slate-200 bg-white p-4 shadow-sm',
    glass: 'rounded-[18px] border border-slate-200 bg-white/90 p-6 shadow-[0_8px_24px_rgba(15,23,42,0.06)] backdrop-blur-sm',
    panel: 'rounded-[16px] border border-slate-200 bg-white p-6 shadow-[0_12px_30px_rgba(15,23,42,0.06)]',
  }

  return (
    <div className={[variants[variant] ?? variants.surface, className].join(' ')} {...rest}>
      {children}
    </div>
  )
}

export default Card
