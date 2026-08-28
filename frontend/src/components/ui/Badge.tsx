import React from 'react'

interface BadgeProps {
  children: React.ReactNode
  tone?: 'info' | 'success' | 'warning' | 'danger' | 'neutral'
}

export function Badge({ children, tone = 'neutral' }: BadgeProps) {
  const tones: Record<string,string> = {
    info: 'bg-sky-50 text-sky-700 ring-sky-100',
    success: 'bg-emerald-50 text-emerald-700 ring-emerald-100',
    warning: 'bg-amber-50 text-amber-700 ring-amber-100',
    danger: 'bg-red-50 text-red-700 ring-red-100',
    neutral: 'bg-slate-100 text-slate-700 ring-slate-100',
  }
  return <span className={[ 'inline-flex items-center gap-2 rounded-full px-2 py-0.5 text-xs font-medium ring-1', tones[tone] ].join(' ')}>{children}</span>
}

export default Badge
