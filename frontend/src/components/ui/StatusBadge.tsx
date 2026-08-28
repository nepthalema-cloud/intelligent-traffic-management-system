type Status = string

const variants: Record<string, string> = {
  reported:      'bg-yellow-50 text-yellow-700 ring-yellow-200',
  investigating: 'bg-orange-50 text-orange-700 ring-orange-200',
  managing:      'bg-red-50 text-red-700 ring-red-200',
  resolved:      'bg-emerald-50 text-emerald-700 ring-emerald-200',
  closed:        'bg-slate-100 text-slate-500 ring-slate-200',
  active:        'bg-emerald-50 text-emerald-700 ring-emerald-200',
  inactive:      'bg-slate-100 text-slate-500 ring-slate-200',
  online:        'bg-emerald-50 text-emerald-700 ring-emerald-200',
  offline:       'bg-red-50 text-red-700 ring-red-200',
  degraded:      'bg-amber-50 text-amber-700 ring-amber-200',
  unknown:       'bg-slate-100 text-slate-500 ring-slate-200',
  issued:        'bg-blue-50 text-blue-700 ring-blue-200',
  contested:     'bg-purple-50 text-purple-700 ring-purple-200',
  adjudicated:   'bg-slate-100 text-slate-600 ring-slate-200',
}

const dots: Record<string, string> = {
  active: 'bg-emerald-500', reported: 'bg-yellow-500', investigating: 'bg-orange-500',
  managing: 'bg-red-500', resolved: 'bg-emerald-500', offline: 'bg-red-500',
  degraded: 'bg-amber-500', online: 'bg-emerald-500',
}

interface StatusBadgeProps {
  status: Status
  label?: string
  dot?: boolean
}

export function StatusBadge({ status, label, dot = false }: StatusBadgeProps) {
  const cls = variants[status] ?? 'bg-slate-100 text-slate-600 ring-slate-200'
  const dotCls = dots[status] ?? 'bg-slate-400'
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${cls}`}>
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${dotCls}`} />}
      {label ?? status}
    </span>
  )
}
