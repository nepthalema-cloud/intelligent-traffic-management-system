interface StatCardProps {
  label: string
  value: string | number
  icon: React.ReactNode
  trend?: { value: string; positive: boolean }
  sub?: string
  accent?: 'blue' | 'red' | 'amber' | 'green' | 'slate'
}

const accents = {
  blue:  { bg: 'bg-blue-50',   icon: 'bg-blue-100 text-blue-600',  value: 'text-blue-700' },
  red:   { bg: 'bg-red-50',    icon: 'bg-red-100 text-red-600',    value: 'text-red-700'  },
  amber: { bg: 'bg-amber-50',  icon: 'bg-amber-100 text-amber-600',value: 'text-amber-700'},
  green: { bg: 'bg-emerald-50',icon: 'bg-emerald-100 text-emerald-600', value: 'text-emerald-700' },
  slate: { bg: 'bg-white',     icon: 'bg-slate-100 text-slate-600', value: 'text-slate-800' },
}

export function StatCard({ label, value, icon, trend, sub, accent = 'slate' }: StatCardProps) {
  const a = accents[accent]
  return (
    <div className={`card card-hover rounded-xl p-4 ${a.bg}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</p>
          <p className={`mt-1 text-2xl font-bold ${a.value}`}>{value}</p>
          {sub && <p className="mt-0.5 text-xs text-slate-400">{sub}</p>}
          {trend && (
            <p className={`mt-1 text-xs font-medium ${trend.positive ? 'text-emerald-600' : 'text-red-500'}`}>
              {trend.positive ? '↑' : '↓'} {trend.value}
            </p>
          )}
        </div>
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${a.icon}`}>
          {icon}
        </span>
      </div>
    </div>
  )
}
