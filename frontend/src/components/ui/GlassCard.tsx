import React from 'react'

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

export function GlassCard({ className = '', children, ...rest }: GlassCardProps) {
  return (
    <div
      className={['rounded-[24px] border border-white/10 bg-slate-950/72 p-8 shadow-[0_30px_80px_rgba(1,12,30,0.35)] backdrop-blur-3xl', className].join(' ')}
      {...rest}
    >
      {children}
    </div>
  )
}
