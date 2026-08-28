import { useEffect, useState } from 'react'
import { roadsService } from '@/services/roads.service'
import type { Road, Intersection } from '@/types/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { StatusBadge } from '@/components/ui/StatusBadge'

const ROAD_TYPE_COLOUR: Record<string, string> = {
  arterial:    'bg-blue-50 text-blue-700',
  collector:   'bg-violet-50 text-violet-700',
  local:       'bg-slate-100 text-slate-600',
  highway:     'bg-orange-50 text-orange-700',
  motorway:    'bg-red-50 text-red-700',
}

export function RoadsPage() {
  const [roads, setRoads]               = useState<Road[]>([])
  const [intersections, setIntersections] = useState<Intersection[]>([])
  const [loading, setLoading]           = useState(true)
  const [error, setError]               = useState<string | null>(null)

  async function load() {
    setLoading(true); setError(null)
    try {
      const [rd, int] = await Promise.allSettled([
        roadsService.listRoads({ page_size: 50 }),
        roadsService.listIntersections({ page_size: 50 }),
      ])
      if (rd.status === 'fulfilled')  setRoads(rd.value.results)
      if (int.status === 'fulfilled') setIntersections(int.value.results)
      if (rd.status === 'rejected' && int.status === 'rejected') setError('Could not load road network data.')
    } finally { setLoading(false) }
  }

  useEffect(() => { void load() }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Road Network</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {roads.length} roads · {intersections.length} intersections
        </p>
      </div>

      {loading && <LoadingSpinner />}
      {!loading && error && <ErrorMessage message={error} onRetry={load} />}

      {!loading && !error && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Roads */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-blue-50">
                <svg className="h-3.5 w-3.5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                </svg>
              </div>
              <h2 className="text-sm font-semibold text-slate-700">Roads</h2>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">{roads.length}</span>
            </div>
            {roads.length === 0
              ? <EmptyState icon="🛣️" title="No roads" />
              : (
                <div className="space-y-2">
                  {roads.map(road => (
                    <div key={road.id} className="card rounded-xl px-4 py-3 flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-slate-900">{road.name}</p>
                        {road.description && <p className="text-xs text-slate-500 truncate mt-0.5">{road.description}</p>}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${ROAD_TYPE_COLOUR[road.road_type] ?? 'bg-slate-100 text-slate-600'}`}>
                          {road.road_type}
                        </span>
                        <StatusBadge status={road.is_active ? 'active' : 'inactive'} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
          </div>

          {/* Intersections */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-emerald-50">
                <svg className="h-3.5 w-3.5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </div>
              <h2 className="text-sm font-semibold text-slate-700">Intersections</h2>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">{intersections.length}</span>
            </div>
            {intersections.length === 0
              ? <EmptyState icon="🔀" title="No intersections" />
              : (
                <div className="space-y-2">
                  {intersections.map(inter => (
                    <div key={inter.id} className="card rounded-xl px-4 py-3 flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-slate-900">{inter.name}</p>
                        {inter.latitude != null && (
                          <p className="text-xs font-mono text-slate-400 mt-0.5">
                            {inter.latitude.toFixed(4)}, {inter.longitude!.toFixed(4)}
                          </p>
                        )}
                      </div>
                      <StatusBadge status={inter.is_active ? 'active' : 'inactive'} />
                    </div>
                  ))}
                </div>
              )}
          </div>
        </div>
      )}
    </div>
  )
}
