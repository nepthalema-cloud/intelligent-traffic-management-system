import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { measurementService } from '@/services/traffic.service'
import type { TrafficMeasurement } from '@/types/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { formatRelative } from '@/utils/time'

function speedCls(s: number | null) {
  if (s === null) return 'text-slate-400'
  if (s < 20) return 'text-red-600 font-semibold'
  if (s < 50) return 'text-amber-600'
  return 'text-emerald-600'
}

export function MeasurementsFeed() {
  const [items, setItems]     = useState<TrafficMeasurement[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    measurementService.list({ page_size: 8 })
      .then(d => setItems(d.results))
      .catch(() => setError('Could not load measurements.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="card rounded-xl p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="section-title">Live Measurements</h3>
        <Link to="/measurements" className="text-link">View all →</Link>
      </div>

      {loading && <LoadingSpinner size="sm" />}
      {!loading && error && <ErrorMessage message={error} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState icon="📡" title="No measurements" subtitle="Awaiting sensor data" />
      )}
      {!loading && !error && items.length > 0 && (
        <div className="overflow-x-auto -mx-1">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-100 text-left text-slate-500">
                <th className="pb-2 pl-1 font-medium">Camera</th>
                <th className="pb-2 text-right font-medium">Vehicles</th>
                <th className="pb-2 text-right font-medium">Speed</th>
                <th className="pb-2 text-right font-medium">Occ</th>
                <th className="pb-2 text-right font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {items.map(m => (
                <tr key={m.id} className="border-b border-slate-50 last:border-0">
                  <td className="py-1.5 pl-1 text-slate-700 truncate max-w-[90px]">
                    {m.camera_name ?? m.sensor_name ?? `#${m.camera ?? m.sensor}`}
                  </td>
                  <td className="py-1.5 text-right text-slate-700">{m.vehicle_count ?? '—'}</td>
                  <td className={`py-1.5 text-right ${speedCls(m.avg_speed_kmh)}`}>
                    {m.avg_speed_kmh != null ? `${m.avg_speed_kmh.toFixed(0)}` : '—'}
                  </td>
                  <td className="py-1.5 text-right text-slate-600">
                    {m.occupancy_pct != null ? `${m.occupancy_pct.toFixed(0)}%` : '—'}
                  </td>
                  <td className="py-1.5 text-right text-slate-400">{formatRelative(m.measured_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
