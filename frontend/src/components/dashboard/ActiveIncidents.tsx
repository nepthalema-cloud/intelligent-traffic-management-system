import { useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { incidentService } from '@/services/traffic.service'
import type { TrafficIncident } from '@/types/api'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { usePolling } from '@/hooks/usePolling'
import { formatRelative } from '@/utils/time'

const TYPE_ICON: Record<string, string> = {
  accident: '💥', road_closure: '🚧', hazard: '⚠️', flooding: '🌊', fire: '🔥', other: '📌',
}

interface Props { pollInterval?: number }

export function ActiveIncidents({ pollInterval = 0 }: Props) {
  const [items, setItems]     = useState<TrafficIncident[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)

  const load = useCallback(async () => {
    if (items.length === 0) setLoading(true)
    setError(null)
    try {
      const data = await incidentService.list({ page_size: 6, is_active: 1 })
      setItems(data.results.filter(i => i.state !== 'closed'))
    } catch { setError('Could not load incidents.') }
    finally { setLoading(false) }
  }, [items.length])

  usePolling(load, pollInterval || 9999999, true)

  return (
    <div className="card rounded-xl p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="section-title flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded bg-red-100 text-red-600">
            <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" /></svg>
          </span>
          Active Incidents
        </h3>
        <Link to="/incidents" className="text-link">View all →</Link>
      </div>

      {loading && <LoadingSpinner size="sm" />}
      {!loading && error && <ErrorMessage message={error} onRetry={load} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState icon="✅" title="No active incidents" subtitle="All clear" />
      )}
      {!loading && !error && items.length > 0 && (
        <ul className="space-y-2" role="list">
          {items.map(inc => (
            <li key={inc.id} className="flex items-start justify-between gap-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2.5 hover:bg-slate-100 transition-colors">
              <div className="flex items-start gap-2.5 min-w-0">
                <span className="mt-0.5 text-sm" aria-hidden="true">{TYPE_ICON[inc.incident_type] ?? '📌'}</span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-900">{inc.title}</p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {inc.intersection_name ?? '—'} · {formatRelative(inc.occurred_at)}
                  </p>
                </div>
              </div>
              <StatusBadge status={inc.state} dot />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
