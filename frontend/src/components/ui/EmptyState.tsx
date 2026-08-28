import React from 'react'

interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  subtitle?: string
  action?: React.ReactNode
}

export function EmptyState({ icon, title, description, subtitle, action }: EmptyStateProps) {
  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50 p-6 text-center">
      {icon && <div className="mb-3 text-3xl text-slate-400">{icon}</div>}
      <div className="text-lg font-semibold text-slate-800">{title}</div>
      {description && <p className="mt-2 text-sm text-slate-500">{description}</p>}
      {subtitle && <p className="mt-1 text-xs text-slate-400">{subtitle}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export default EmptyState
