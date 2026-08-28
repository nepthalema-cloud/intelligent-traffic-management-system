import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, BarChart, Bar, Cell,
} from 'recharts'
import { analyticsService } from '@/services/analytics.service'
import type { TrafficFlowSummary, IncidentReportSummary, ViolationSummary } from '@/types/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { tableCls, filterInputCls } from '@/components/ui/DataTable'
import { formatDateTime } from '@/utils/time'

type Tab = 'flow' | 'incidents' | 'violations'

function speedCls(v: number | null) {
  if (v === null) return 'text-slate-400'
  if (v < 20) return 'text-red-600'
  if (v < 50) return 'text-amber-600'
  return 'text-emerald-600'
}

const axisColor = '#94a3b8'
const gridColor = '#f1f5f9'

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

function FlowTab() {
  const [items, setItems]     = useState<TrafficFlowSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)
  const [ptFilter, setPtFilter] = useState('daily')

  useEffect(() => {
    setLoading(true); setError(null)
    analyticsService.listFlow({ period_type: ptFilter, page_size: 50 })
      .then(d => setItems(d.results))
      .catch(() => setError('Could not load flow summaries.'))
      .finally(() => setLoading(false))
  }, [ptFilter])

  const chartData = [...items].reverse().map(r => ({
    label: `${r.segment_name ?? 'All'} ${new Date(r.period_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`,
    speed: r.avg_speed_kmh != null ? +r.avg_speed_kmh.toFixed(1) : null,
  }))

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <select value={ptFilter} onChange={e => setPtFilter(e.target.value)} className={filterInputCls}>
          <option value="hourly">Hourly</option>
          <option value="daily">Daily</option>
        </select>
        <span className="text-sm text-slate-500">{items.length} summaries</span>
      </div>

      {loading && <LoadingSpinner />}
      {!loading && error && <ErrorMessage message={error} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState icon="📊" title="No flow summaries yet"
          subtitle="Run analytics: python manage.py run_analytics --all" />
      )}

      {!loading && !error && items.length > 0 && (
        <>
          <div className="card rounded-xl p-5">
            <p className="section-title mb-4">Average Speed (km/h)</p>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                <XAxis dataKey="label" tick={{ fill: axisColor, fontSize: 9 }} interval="preserveStartEnd" />
                <YAxis tick={{ fill: axisColor, fontSize: 10 }} unit=" km/h" width={64} />
                <Tooltip content={<ChartTip />} />
                <Line type="monotone" dataKey="speed" name="Avg Speed (km/h)"
                  stroke="#2563eb" strokeWidth={2} dot={false} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className={tableCls.wrapper}>
            <table className={tableCls.table}>
              <thead className={tableCls.thead}>
                <tr>
                  <th className={tableCls.th}>Segment</th>
                  <th className={tableCls.th}>Period</th>
                  <th className={tableCls.thRight}>Vehicles</th>
                  <th className={tableCls.thRight}>Avg Speed</th>
                  <th className={tableCls.thRight}>Occupancy</th>
                  <th className={tableCls.thRight}>Samples</th>
                </tr>
              </thead>
              <tbody className={tableCls.tbody}>
                {items.map(r => (
                  <tr key={r.id} className={tableCls.tr}>
                    <td className={tableCls.td}>{r.segment_name ?? <span className="text-slate-400 italic">City-wide</span>}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">{formatDateTime(r.period_start)}</td>
                    <td className={tableCls.tdRight}>{r.total_vehicle_count ?? '—'}</td>
                    <td className={`px-4 py-3 text-right ${speedCls(r.avg_speed_kmh)}`}>
                      {r.avg_speed_kmh != null ? `${r.avg_speed_kmh.toFixed(1)} km/h` : '—'}
                    </td>
                    <td className={tableCls.tdRight}>{r.avg_occupancy_pct != null ? `${r.avg_occupancy_pct.toFixed(1)}%` : '—'}</td>
                    <td className="px-4 py-3 text-right text-slate-400">{r.sample_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

function IncidentsTab() {
  const [items, setItems]     = useState<IncidentReportSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)

  useEffect(() => {
    setLoading(true); setError(null)
    analyticsService.listIncidents({ page_size: 30 })
      .then(d => setItems(d.results))
      .catch(() => setError('Could not load incident reports.'))
      .finally(() => setLoading(false))
  }, [])

  const barData = items.slice(0, 10).map(r => ({ name: r.segment_name ?? 'City-wide', incidents: r.total_incidents }))

  return (
    <div className="space-y-5">
      {loading && <LoadingSpinner />}
      {!loading && error && <ErrorMessage message={error} />}
      {!loading && !error && items.length === 0 && <EmptyState icon="🚨" title="No incident reports yet" />}

      {!loading && !error && items.length > 0 && (
        <>
          <div className="card rounded-xl p-5">
            <p className="section-title mb-4">Incidents by Segment</p>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={barData} margin={{ top: 4, right: 16, bottom: 24, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                <XAxis dataKey="name" tick={{ fill: axisColor, fontSize: 9 }} angle={-20} textAnchor="end" />
                <YAxis tick={{ fill: axisColor, fontSize: 10 }} allowDecimals={false} />
                <Tooltip content={<ChartTip />} />
                <Bar dataKey="incidents" name="Incidents" radius={[4, 4, 0, 0]}>
                  {barData.map((_, i) => <Cell key={i} fill={i === 0 ? '#dc2626' : '#f87171'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className={tableCls.wrapper}>
            <table className={tableCls.table}>
              <thead className={tableCls.thead}>
                <tr>
                  <th className={tableCls.th}>Segment</th>
                  <th className={tableCls.th}>Period</th>
                  <th className={tableCls.thRight}>Total</th>
                  <th className={tableCls.th}>By Type</th>
                  <th className={tableCls.th}>By State</th>
                </tr>
              </thead>
              <tbody className={tableCls.tbody}>
                {items.map(r => (
                  <tr key={r.id} className={tableCls.tr}>
                    <td className={tableCls.td}>{r.segment_name ?? <span className="text-slate-400 italic">City-wide</span>}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">{formatDateTime(r.period_start)}</td>
                    <td className="px-4 py-3 text-right font-semibold text-slate-900">{r.total_incidents}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{Object.entries(r.by_type).map(([k,v]) => `${k}: ${v}`).join(', ') || '—'}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{Object.entries(r.by_state).map(([k,v]) => `${k}: ${v}`).join(', ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

function ViolationsTab() {
  const [items, setItems]     = useState<ViolationSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)

  useEffect(() => {
    setLoading(true); setError(null)
    analyticsService.listViolations({ page_size: 30 })
      .then(d => setItems(d.results))
      .catch(() => setError('Could not load violation summaries.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-5">
      {loading && <LoadingSpinner />}
      {!loading && error && <ErrorMessage message={error} />}
      {!loading && !error && items.length === 0 && <EmptyState icon="🚦" title="No violation summaries yet" />}

      {!loading && !error && items.length > 0 && (
        <div className={tableCls.wrapper}>
          <table className={tableCls.table}>
            <thead className={tableCls.thead}>
              <tr>
                <th className={tableCls.th}>Segment</th>
                <th className={tableCls.th}>Period</th>
                <th className={tableCls.thRight}>Total</th>
                <th className={tableCls.th}>By Type</th>
              </tr>
            </thead>
            <tbody className={tableCls.tbody}>
              {items.map(r => (
                <tr key={r.id} className={tableCls.tr}>
                  <td className={tableCls.td}>{r.segment_name ?? <span className="text-slate-400 italic">City-wide</span>}</td>
                  <td className="px-4 py-3 text-slate-400 text-xs">{formatDateTime(r.period_start)}</td>
                  <td className="px-4 py-3 text-right font-semibold text-slate-900">{r.total_violations}</td>
                  <td className="px-4 py-3 text-xs text-slate-500">{Object.entries(r.by_type).map(([k,v]) => `${k}: ${v}`).join(', ') || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function AnalyticsPage() {
  const [tab, setTab] = useState<Tab>('flow')

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: 'flow',       label: 'Traffic Flow',
      icon: <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg> },
    { key: 'incidents',  label: 'Incidents',
      icon: <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg> },
    { key: 'violations', label: 'Violations',
      icon: <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" /></svg> },
  ]

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Analytics</h1>
        <p className="text-sm text-slate-500 mt-0.5">Pre-aggregated traffic flow, incident, and violation summaries</p>
      </div>

      {/* Tab bar — matches Dashboard screenshot style */}
      <div className="flex gap-1 rounded-xl border border-slate-200 bg-slate-50 p-1 w-fit">
        {tabs.map(t => (
          <button key={t.key} type="button" onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.key ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}>
            <span className={tab === t.key ? 'text-blue-600' : 'text-slate-400'}>{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'flow'       && <FlowTab />}
      {tab === 'incidents'  && <IncidentsTab />}
      {tab === 'violations' && <ViolationsTab />}
    </div>
  )
}
