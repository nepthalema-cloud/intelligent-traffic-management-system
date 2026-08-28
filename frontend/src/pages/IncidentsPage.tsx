import { useEffect, useState } from 'react'
import { incidentService } from '@/services/traffic.service'
import type { TrafficIncident } from '@/types/api'
import { ROLES } from '@/types/api'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { CreateIncidentModal } from '@/components/incidents/CreateIncidentModal'
import { TransitionIncidentModal } from '@/components/incidents/TransitionIncidentModal'
import { EditIncidentModal } from '@/components/incidents/EditIncidentModal'
import { Pagination, tableCls, filterInputCls } from '@/components/ui/DataTable'
import { useAuthStore } from '@/store/authStore'
import { formatDateTime } from '@/utils/time'

const TYPE_LABELS: Record<string, { label: string; colour: string }> = {
  accident:     { label: 'Accident',     colour: 'bg-red-100 text-red-700' },
  road_closure: { label: 'Road Closure', colour: 'bg-orange-100 text-orange-700' },
  hazard:       { label: 'Hazard',       colour: 'bg-amber-100 text-amber-700' },
  flooding:     { label: 'Flooding',     colour: 'bg-blue-100 text-blue-700' },
  fire:         { label: 'Fire',         colour: 'bg-red-100 text-red-800' },
  other:        { label: 'Other',        colour: 'bg-slate-100 text-slate-600' },
}

const STATE_ORDER = ['reported', 'investigating', 'managing', 'resolved', 'closed']
const WRITE_ROLES = [ROLES.SYSTEM_ADMIN, ROLES.TRAFFIC_CONTROL_OFFICER]

export function IncidentsPage() {
  const { hasAnyRole } = useAuthStore()
  const canWrite = hasAnyRole(WRITE_ROLES)

  const [items, setItems]             = useState<TrafficIncident[]>([])
  const [count, setCount]             = useState(0)
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState<string | null>(null)
  const [page, setPage]               = useState(1)
  const [stateFilter, setStateFilter] = useState('')
  const [showCreate, setShowCreate]   = useState(false)
  const [transitionTarget, setTransitionTarget] = useState<TrafficIncident | null>(null)
  const [editTarget, setEditTarget]   = useState<TrafficIncident | null>(null)

  async function load(p = 1) {
    setLoading(true); setError(null)
    try {
      const params: Record<string, string | number> = { page: p, page_size: 20 }
      if (stateFilter) params['state'] = stateFilter
      const data = await incidentService.list(params)
      setItems(data.results); setCount(data.count)
    } catch { setError('Could not load incidents.') }
    finally { setLoading(false) }
  }

  useEffect(() => { setPage(1); void load(1) }, [stateFilter])
  const totalPages = Math.ceil(count / 20)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Traffic Incidents</h1>
          <p className="text-sm text-slate-500 mt-0.5">{count} total</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={stateFilter} onChange={e => setStateFilter(e.target.value)} className={filterInputCls}>
            <option value="">All states</option>
            {STATE_ORDER.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          {canWrite && (
            <button type="button" onClick={() => setShowCreate(true)}
              className="flex items-center gap-1.5 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 shadow-sm transition-colors">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
              Report Incident
            </button>
          )}
        </div>
      </div>

      {loading && <LoadingSpinner />}
      {!loading && error && <ErrorMessage message={error} onRetry={() => load(page)} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState icon="✅" title="No incidents found" subtitle="No incidents match the current filter." />
      )}

      {!loading && !error && items.length > 0 && (
        <div className={tableCls.wrapper}>
          <table className={tableCls.table}>
            <thead className={tableCls.thead}>
              <tr>
                <th className={tableCls.th}>Title</th>
                <th className={tableCls.th}>Type</th>
                <th className={tableCls.th}>State</th>
                <th className={tableCls.th}>Location</th>
                <th className={tableCls.th}>Occurred</th>
                {canWrite && <th className={tableCls.th}>Actions</th>}
              </tr>
            </thead>
            <tbody className={tableCls.tbody}>
              {items.map(inc => {
                const type = TYPE_LABELS[inc.incident_type] ?? { label: inc.incident_type, colour: 'bg-slate-100 text-slate-600' }
                return (
                  <tr key={inc.id} className={tableCls.tr}>
                    <td className="px-4 py-3 font-medium text-slate-900 max-w-xs">
                      <span className="line-clamp-2">{inc.title}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${type.colour}`}>
                        {type.label}
                      </span>
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={inc.state} dot /></td>
                    <td className="px-4 py-3 text-slate-500 truncate max-w-[140px] text-sm">
                      {inc.intersection_name ?? (inc.segment_ids.length > 0 ? `${inc.segment_ids.length} segment(s)` : '—')}
                    </td>
                    <td className="px-4 py-3 text-slate-400 whitespace-nowrap text-xs">
                      {formatDateTime(inc.occurred_at)}
                    </td>
                    {canWrite && (
                      <td className="px-4 py-3">
                        <div className="flex gap-1.5">
                          <button type="button" onClick={() => setEditTarget(inc)}
                            className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors">
                            Edit
                          </button>
                          {inc.state !== 'closed' && (
                            <button type="button" onClick={() => setTransitionTarget(inc)}
                              className="rounded-md border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors whitespace-nowrap">
                              Update state
                            </button>
                          )}
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

      <CreateIncidentModal open={showCreate} onClose={() => setShowCreate(false)} onCreated={() => void load(1)} />
      {editTarget && (
        <EditIncidentModal incident={editTarget} open={!!editTarget}
          onClose={() => setEditTarget(null)}
          onSaved={u => { setItems(prev => prev.map(i => i.id === u.id ? u : i)); setEditTarget(null) }} />
      )}
      {transitionTarget && (
        <TransitionIncidentModal incident={transitionTarget} open={!!transitionTarget}
          onClose={() => setTransitionTarget(null)}
          onTransitioned={u => setItems(prev => prev.map(i => i.id === u.id ? u : i))} />
      )}
    </div>
  )
}
