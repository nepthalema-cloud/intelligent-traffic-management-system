import { useEffect, useState } from 'react'
import { eventService } from '@/services/traffic.service'
import type { TrafficEvent } from '@/types/api'
import { ROLES } from '@/types/api'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { CreateEventModal } from '@/components/events/CreateEventModal'
import { EditEventModal } from '@/components/events/EditEventModal'
import { Pagination, tableCls } from '@/components/ui/DataTable'
import { useAuthStore } from '@/store/authStore'
import { formatDateTime } from '@/utils/time'

const EVENT_TYPE_CONFIG: Record<string, { label: string; dot: string; text: string }> = {
  congestion:   { label: 'Congestion',   dot: 'bg-red-400',    text: 'text-red-700'    },
  incident:     { label: 'Incident',     dot: 'bg-orange-400', text: 'text-orange-700' },
  roadwork:     { label: 'Roadwork',     dot: 'bg-amber-400',  text: 'text-amber-700'  },
  weather:      { label: 'Weather',      dot: 'bg-sky-400',    text: 'text-sky-700'    },
  signal_fault: { label: 'Signal Fault', dot: 'bg-purple-400', text: 'text-purple-700' },
  other:        { label: 'Other',        dot: 'bg-slate-400',  text: 'text-slate-600'  },
}

const WRITE_ROLES = [ROLES.SYSTEM_ADMIN, ROLES.TRAFFIC_CONTROL_OFFICER]

export function EventsPage() {
  const { hasAnyRole } = useAuthStore()
  const canWrite = hasAnyRole(WRITE_ROLES)

  const [items, setItems]   = useState<TrafficEvent[]>([])
  const [count, setCount]   = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState<string | null>(null)
  const [page, setPage]     = useState(1)
  const [showCreate, setShowCreate] = useState(false)
  const [toggling, setToggling]     = useState<number | null>(null)
  const [editTarget, setEditTarget] = useState<TrafficEvent | null>(null)

  async function load(p = 1) {
    setLoading(true); setError(null)
    try {
      const data = await eventService.list({ page: p, page_size: 20 })
      setItems(data.results); setCount(data.count)
    } catch { setError('Could not load events.') }
    finally { setLoading(false) }
  }

  useEffect(() => { void load(1) }, [])

  async function toggleActive(ev: TrafficEvent) {
    setToggling(ev.id)
    try {
      const updated = await eventService.setActive(ev.id, !ev.is_active)
      setItems(prev => prev.map(e => e.id === updated.id ? updated : e))
    } catch { /* silent */ }
    finally { setToggling(null) }
  }

  const totalPages = Math.ceil(count / 20)

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Traffic Events</h1>
          <p className="text-sm text-slate-500 mt-0.5">{count} total events</p>
        </div>
        {canWrite && (
          <button type="button" onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-600 shadow-sm transition-colors">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Log Event
          </button>
        )}
      </div>

      {loading && <LoadingSpinner />}
      {!loading && error && <ErrorMessage message={error} onRetry={() => load(page)} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState icon="📭" title="No events found" subtitle="No traffic events have been logged yet." />
      )}

      {!loading && !error && items.length > 0 && (
        <div className={tableCls.wrapper}>
          <table className={tableCls.table}>
            <thead className={tableCls.thead}>
              <tr>
                <th className={tableCls.th}>Type</th>
                <th className={tableCls.th}>Description</th>
                <th className={tableCls.th}>Location</th>
                <th className={tableCls.th}>Status</th>
                <th className={tableCls.th}>Occurred</th>
                {canWrite && <th className={tableCls.th}>Actions</th>}
              </tr>
            </thead>
            <tbody className={tableCls.tbody}>
              {items.map(ev => {
                const cfg = EVENT_TYPE_CONFIG[ev.event_type] ?? EVENT_TYPE_CONFIG.other
                return (
                  <tr key={ev.id} className={tableCls.tr}>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-2 whitespace-nowrap">
                        <span className={`h-2 w-2 rounded-full shrink-0 ${cfg.dot}`} />
                        <span className={`text-sm font-medium ${cfg.text}`}>{cfg.label}</span>
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700 max-w-xs">
                      <span className="line-clamp-2">{ev.description}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-500 truncate max-w-[160px] text-sm">
                      {ev.intersection_name ?? ev.segment_road_name ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={ev.is_active ? 'active' : 'inactive'} dot />
                    </td>
                    <td className="px-4 py-3 text-slate-400 whitespace-nowrap text-xs">
                      {formatDateTime(ev.occurred_at)}
                    </td>
                    {canWrite && (
                      <td className="px-4 py-3">
                        <div className="flex gap-1.5">
                          <button type="button" onClick={() => setEditTarget(ev)}
                            className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors">
                            Edit
                          </button>
                          <button type="button" disabled={toggling === ev.id}
                            onClick={() => toggleActive(ev)}
                            className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-50 whitespace-nowrap ${
                              ev.is_active
                                ? 'border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
                                : 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                            }`}>
                            {toggling === ev.id ? '…' : ev.is_active ? 'Deactivate' : 'Reactivate'}
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <Pagination page={page} totalPages={totalPages} total={count}
        onPrev={() => { const p = page-1; setPage(p); void load(p) }}
        onNext={() => { const p = page+1; setPage(p); void load(p) }} />

      <CreateEventModal open={showCreate} onClose={() => setShowCreate(false)} onCreated={() => void load(1)} />
      {editTarget && (
        <EditEventModal event={editTarget} open={!!editTarget}
          onClose={() => setEditTarget(null)}
          onSaved={u => { setItems(prev => prev.map(e => e.id === u.id ? u : e)); setEditTarget(null) }} />
      )}
    </div>
  )
}
