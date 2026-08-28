import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { signalService } from '@/services/traffic.service'
import type { TrafficSignal } from '@/types/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorMessage } from '@/components/ui/ErrorMessage'

export function SignalStatusList() {
  const [items, setItems]     = useState<TrafficSignal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    signalService.list({ page_size: 8 })
      .then(d => setItems(d.results))
      .catch(() => setError('Could not load signals.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="card rounded-xl p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="section-title">Traffic Signals</h3>
        <Link to="/signals" className="text-link">View all →</Link>
      </div>

      {loading && <LoadingSpinner size="sm" />}
      {!loading && error && <ErrorMessage message={error} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState icon="🚦" title="No signals configured" />
      )}
      {!loading && !error && items.length > 0 && (
        <ul className="space-y-1.5" role="list">
          {items.map(sig => (
            <li key={sig.id} className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-900">{sig.name}</p>
                <p className="text-xs text-slate-500 truncate">{sig.intersection_name}</p>
              </div>
              <span className={`ml-2 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] ${sig.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-500'}`}>
                {sig.is_active ? '●' : '○'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
