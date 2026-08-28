import { useState, useCallback, useEffect } from 'react'
import { StatCard } from '@/components/ui/StatCard'
import { ActiveIncidents } from '@/components/dashboard/ActiveIncidents'
import { RecentEvents } from '@/components/dashboard/RecentEvents'
import { MeasurementsFeed } from '@/components/dashboard/MeasurementsFeed'
import { SignalStatusList } from '@/components/dashboard/SignalStatusList'
import { CameraHealthSummary } from '@/components/dashboard/CameraHealthSummary'
import { TrafficMap } from '@/components/map/TrafficMap'
import { incidentService, eventService, signalService } from '@/services/traffic.service'
import { cameraService } from '@/services/cameras.service'
import { useAuthStore } from '@/store/authStore'
import { usePolling } from '@/hooks/usePolling'
import { useWebSocket } from '@/hooks/useWebSocket'

const POLL = 30_000

const IcAlert = <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
const IcEvent = <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
const IcSig = <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" /></svg>
const IcCam = <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.069A1 1 0 0121 8.871v6.258a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>

interface Stats { activeIncidents: number; activeEvents: number; totalSignals: number; totalCameras: number; lastUpdated: Date }

export function DashboardPage() {
  const { user } = useAuthStore()
  const [stats, setStats]               = useState<Stats | null>(null)
  const [wsConnected, setWsConnected]   = useState(false)
  const [lastWsEvent, setLastWsEvent]   = useState<string | null>(null)

  const loadStats = useCallback(async () => {
    const [inc, evt, sig, cam] = await Promise.allSettled([
      incidentService.list({ page_size: 1, is_active: 1 }),
      eventService.list({ page_size: 1 }),
      signalService.list({ page_size: 1 }),
      cameraService.list({ page_size: 1 }),
    ])
    setStats({
      activeIncidents: inc.status === 'fulfilled' ? inc.value.count : 0,
      activeEvents:    evt.status === 'fulfilled' ? evt.value.count : 0,
      totalSignals:    sig.status === 'fulfilled' ? sig.value.count : 0,
      totalCameras:    cam.status === 'fulfilled' ? cam.value.count : 0,
      lastUpdated: new Date(),
    })
  }, [])

  usePolling(loadStats, POLL)

  // WebSocket: receive real-time pushes from the backend
  const handleWsMessage = useCallback((type: string, _payload: unknown) => {
    setLastWsEvent(type)
    // On measurement_created: refresh stats immediately
    if (type === 'measurement_created' || type === 'incident_updated') {
      void loadStats()
    }
  }, [loadStats])

  const { connected } = useWebSocket({
    path: 'dashboard',
    onMessage: handleWsMessage,
    enabled: true,
  })

  useEffect(() => { setWsConnected(connected) }, [connected])

  const now     = new Date()
  const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const dateStr = now.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">
            {user?.first_name ? `Welcome back, ${user.first_name}` : 'Traffic Operations Overview'}
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            {user?.roles[0] ?? 'Traffic Management'} · Real-time monitoring
          </p>
        </div>
        <div className="hidden sm:block text-right shrink-0">
          <p className="text-sm font-semibold text-slate-800">{timeStr}</p>
          <p className="text-xs text-slate-500">{dateStr}</p>
          {/* WebSocket connection indicator */}
          <div className="flex items-center justify-end gap-1.5 mt-1">
            <span className={`h-1.5 w-1.5 rounded-full ${wsConnected ? 'bg-emerald-400' : 'bg-slate-300'}`} />
            <span className="text-[10px] text-slate-400">
              {wsConnected ? 'Real-time connected' : 'Polling only'}
            </span>
          </div>
          {stats && (
            <p className="text-[10px] text-slate-400">
              Updated {stats.lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              {lastWsEvent && <span className="ml-1 text-blue-400">· WS: {lastWsEvent}</span>}
            </p>
          )}
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Active Incidents" value={stats?.activeIncidents ?? '—'} icon={IcAlert}
          accent={stats && stats.activeIncidents > 0 ? 'red' : 'green'}
          sub={stats?.activeIncidents === 0 ? 'All clear' : 'Requires attention'} />
        <StatCard label="Active Events" value={stats?.activeEvents ?? '—'} icon={IcEvent}
          accent={stats && stats.activeEvents > 0 ? 'amber' : 'slate'} />
        <StatCard label="Traffic Signals" value={stats?.totalSignals ?? '—'} icon={IcSig} accent="blue" />
        <StatCard label="Cameras Online" value={stats?.totalCameras ?? '—'} icon={IcCam} accent="slate" />
      </div>

      {/* Map */}
      <div className="card rounded-xl overflow-hidden" style={{ height: 420 }}>
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h3 className="section-title">Traffic Map — Gondar, Ethiopia</h3>
          <span className="flex items-center gap-1.5 text-xs text-slate-500">
            <span className={`h-1.5 w-1.5 rounded-full ${wsConnected ? 'bg-emerald-400 animate-pulse' : 'bg-slate-300'}`} />
            {wsConnected ? 'Live' : 'Polling'}
          </span>
        </div>
        <div style={{ height: 372 }}>
          <TrafficMap compact />
        </div>
      </div>

      {/* Incidents + Events */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ActiveIncidents pollInterval={POLL} />
        <RecentEvents    pollInterval={POLL} />
      </div>

      {/* Measurements + Signals + Cameras */}
      <div className="grid gap-4 lg:grid-cols-3">
        <MeasurementsFeed />
        <SignalStatusList />
        <CameraHealthSummary />
      </div>
    </div>
  )
}
