import { useEffect, useState, useMemo } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip,
} from 'recharts'
import { measurementService } from '@/services/traffic.service'
import { cameraService, sensorService } from '@/services/cameras.service'
import type { TrafficMeasurement, Camera, Sensor } from '@/types/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { Pagination, tableCls, filterInputCls } from '@/components/ui/DataTable'
import { formatDateTime } from '@/utils/time'

function speedCls(speed: number | null) {
  if (speed === null) return 'text-slate-400'
  if (speed < 20) return 'text-red-600 font-semibold'
  if (speed < 50) return 'text-amber-600'
  return 'text-emerald-600'
}

/* Light-theme chart tooltip */
function ChartTip({ active, payload, label }: {
  active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-semibold text-slate-700">{label}</p>
      {payload.map(p => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: <strong>{typeof p.value === 'number' ? p.value.toFixed(1) : p.value}</strong>
        </p>
      ))}
    </div>
  )
}

export function MeasurementsPage() {
  const [items, setItems]       = useState<TrafficMeasurement[]>([])
  const [count, setCount]       = useState(0)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState<string | null>(null)
  const [page, setPage]         = useState(1)
  const [cameras, setCameras]   = useState<Camera[]>([])
  const [sensors, setSensors]   = useState<Sensor[]>([])
  const [camFilter, setCamFilter] = useState<string>('')
  const [view, setView]         = useState<'chart' | 'table'>('chart')

  useEffect(() => {
    Promise.allSettled([
      cameraService.list({ page_size: 100 }),
      sensorService.list({ page_size: 100 }),
    ]).then(([c, s]) => {
      if (c.status === 'fulfilled') setCameras(c.value.results)
      if (s.status === 'fulfilled') setSensors(s.value.results)
    })
  }, [])

  async function load(p = 1) {
    setLoading(true); setError(null)
    try {
      const params: Record<string, string | number> = { page: p, page_size: 50 }
      if (camFilter) {
        const [type, id] = camFilter.split(':')
        if (type === 'cam') params['camera'] = id
        if (type === 'sen') params['sensor'] = id
      }
      const data = await measurementService.list(params)
      setItems(data.results); setCount(data.count)
    } catch { setError('Could not load measurements.') }
    finally { setLoading(false) }
  }

  useEffect(() => { setPage(1); void load(1) }, [camFilter])

  const chartData = useMemo(() => [...items].reverse().map(m => ({
    time:  new Date(m.measured_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    speed: m.avg_speed_kmh  != null ? Math.round(m.avg_speed_kmh)  : null,
    count: m.vehicle_count  ?? null,
    occ:   m.occupancy_pct  != null ? Math.round(m.occupancy_pct)  : null,
  })), [items])

  const totalPages = Math.ceil(count / 50)
  const speeds = items.map(m => m.avg_speed_kmh).filter((v): v is number => v != null)
  const counts = items.map(m => m.vehicle_count).filter((v): v is number => v != null)
  const avgSpeed = speeds.length ? (speeds.reduce((a,b) => a+b, 0) / speeds.length).toFixed(1) : null
  const totalVeh = counts.reduce((a,b) => a+b, 0)

  /* Light chart axis/grid colours */
  const axisColor = '#94a3b8'   // slate-400
  const gridColor = '#f1f5f9'   // slate-100

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Traffic Measurements</h1>
          <p className="text-sm text-slate-500 mt-0.5">{count} readings · newest first</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select value={camFilter} onChange={e => setCamFilter(e.target.value)}
            className={filterInputCls} aria-label="Filter by source">
            <option value="">All sources</option>
            {cameras.map(c => <option key={`cam:${c.id}`} value={`cam:${c.id}`}>📷 {c.name}</option>)}
            {sensors.map(s => <option key={`sen:${s.id}`} value={`sen:${s.id}`}>📡 {s.name}</option>)}
          </select>
          <div className="flex rounded-lg border border-slate-200 bg-slate-50 p-0.5">
            {(['chart', 'table'] as const).map(v => (
              <button key={v} type="button" onClick={() => setView(v)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  view === v ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                }`}>
                {v === 'chart' ? 'Charts' : 'Table'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Summary cards */}
      {!loading && items.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: 'Avg Speed', value: avgSpeed ? `${avgSpeed} km/h` : '—',
              colour: avgSpeed && Number(avgSpeed) < 20 ? 'text-red-600' : avgSpeed && Number(avgSpeed) < 50 ? 'text-amber-600' : 'text-emerald-600',
              bg: 'bg-white' },
            { label: 'Total Vehicles', value: totalVeh.toLocaleString(), colour: 'text-blue-700', bg: 'bg-blue-50' },
            { label: 'Readings', value: items.length.toString(), colour: 'text-slate-700', bg: 'bg-white' },
          ].map(s => (
            <div key={s.label} className={`card rounded-xl px-5 py-4 ${s.bg}`}>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{s.label}</p>
              <p className={`text-2xl font-bold mt-1 ${s.colour}`}>{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {loading && <LoadingSpinner />}
      {!loading && error && <ErrorMessage message={error} onRetry={() => load(page)} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState icon="📡" title="No measurements" subtitle="No sensor data available for the selected source." />
      )}

      {/* Chart view */}
      {!loading && !error && items.length > 0 && view === 'chart' && (
        <div className="space-y-4">
          <div className="card rounded-xl p-5">
            <p className="section-title mb-4">Average Speed (km/h)</p>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                <XAxis dataKey="time" tick={{ fill: axisColor, fontSize: 11 }} />
                <YAxis tick={{ fill: axisColor, fontSize: 11 }} unit=" km/h" width={64} />
                <Tooltip content={<ChartTip />} />
                <Line type="monotone" dataKey="speed" name="Avg Speed (km/h)"
                  stroke="#2563eb" strokeWidth={2} dot={false} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="card rounded-xl p-5">
              <p className="section-title mb-4">Vehicle Count</p>
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                  <XAxis dataKey="time" tick={{ fill: axisColor, fontSize: 10 }} />
                  <YAxis tick={{ fill: axisColor, fontSize: 10 }} width={36} />
                  <Tooltip content={<ChartTip />} />
                  <Line type="monotone" dataKey="count" name="Vehicles"
                    stroke="#7c3aed" strokeWidth={2} dot={false} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="card rounded-xl p-5">
              <p className="section-title mb-4">Lane Occupancy (%)</p>
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                  <XAxis dataKey="time" tick={{ fill: axisColor, fontSize: 10 }} />
                  <YAxis tick={{ fill: axisColor, fontSize: 10 }} unit="%" width={36} domain={[0, 100]} />
                  <Tooltip content={<ChartTip />} />
                  <Line type="monotone" dataKey="occ" name="Occupancy %"
                    stroke="#d97706" strokeWidth={2} dot={false} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* Table view */}
      {!loading && !error && items.length > 0 && view === 'table' && (
        <div className={tableCls.wrapper}>
          <table className={tableCls.table}>
            <thead className={tableCls.thead}>
              <tr>
                <th className={tableCls.th}>Source</th>
                <th className={tableCls.th}>Segment</th>
                <th className={tableCls.thRight}>Vehicles</th>
                <th className={tableCls.thRight}>Avg Speed</th>
                <th className={tableCls.thRight}>Occupancy</th>
                <th className={tableCls.th}>Measured at</th>
              </tr>
            </thead>
            <tbody className={tableCls.tbody}>
              {items.map(m => (
                <tr key={m.id} className={tableCls.tr}>
                  <td className={tableCls.td}>{m.camera_name ?? m.sensor_name ?? `#${m.camera ?? m.sensor}`}</td>
                  <td className="px-4 py-3 text-slate-500 truncate max-w-[120px] text-sm">{m.segment_name ?? '—'}</td>
                  <td className={tableCls.tdRight}>{m.vehicle_count ?? '—'}</td>
                  <td className={`px-4 py-3 text-right ${speedCls(m.avg_speed_kmh)}`}>
                    {m.avg_speed_kmh != null ? `${m.avg_speed_kmh.toFixed(1)} km/h` : '—'}
                  </td>
                  <td className={tableCls.tdRight}>{m.occupancy_pct != null ? `${m.occupancy_pct.toFixed(1)}%` : '—'}</td>
                  <td className="px-4 py-3 text-slate-400 whitespace-nowrap text-xs">{formatDateTime(m.measured_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Pagination page={page} totalPages={totalPages} total={count}
        onPrev={() => { const p = page-1; setPage(p); void load(p) }}
        onNext={() => { const p = page+1; setPage(p); void load(p) }} />
    </div>
  )
}
