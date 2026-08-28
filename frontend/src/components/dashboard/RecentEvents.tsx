import { useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { eventService } from '@/services/traffic.service'
import type { TrafficEvent } from '@/types/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { usePolling } from '@/hooks/usePolling'
import { formatRelative } from '@/utils/time'

const EVENT_COLOURS: Record<string, string> = {
  congestion:   'bg-red-100 text-red-600',
  incident:     'bg-orange-100 text-orange-600',
  roadwork:     'bg-amber-100 text-amber-600',
  weather:      'bg-sky-100 text-sky-600',
  signal_fault: 'bg-purple-100 text-purple-600',
  other:        'bg-slate-100 text-slate-600',
}
const EVENT_ICONS: Record<string, string> = {
  congestion:'🔴', incident:'🚨', roadwork:'🚧', weather:'🌧️', signal_fault:'🚦', other:'📌',
}

interface Props { pollInterval?: number }

export function RecentEvents({ pollInterval = 0 }: Props) {
  const [items, setItems]     = useState<TrafficEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)

  const load = useCallback(async () => {
    if (items.length === 0) setLoading(true)
    setError(null)
    try {
      const data = await eventService.list({ page_size: 6 })
      setItems(data.results)
    } catch { setError('Could not load events.') }
    finally { setLoading(false) }
  }, [items.length])

  usePolling(load, pollInterval || 9999999, true)

  return (
    <div className="card rounded-xl p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="section-title flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded bg-amber-100 text-amber-600">
            <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" /></svg>
          </span>
          Recent Events
        </h3>
        <Link to="/events" className="text-link">View all →</Link>
      </div>

      {loading && <LoadingSpinner size="sm" />}
      {!loading && error && <ErrorMessage message={error} onRetry={load} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState icon="📭" title="No recent events" />
      )}
      {!loading && !error && items.length > 0 && (
        <ul className="space-y-2" role="list">
          {items.map(ev => (
            <li key={ev.id} className="flex items-start gap-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2.5">
              <span className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-xs ${EVENT_COLOURS[ev.event_type] ?? 'bg-slate-100 text-slate-600'}`}>
                {EVENT_ICONS[ev.event_type] ?? '📌'}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm text-slate-800">{ev.description}</p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {ev.intersection_name ?? ev.segment_road_name ?? 'Unknown location'}
                  {' · '}{formatRelative(ev.occurred_at)}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
