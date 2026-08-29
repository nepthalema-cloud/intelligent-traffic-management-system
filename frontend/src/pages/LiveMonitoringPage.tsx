import { useEffect, useMemo, useRef, useState } from 'react'
import { cameraService } from '@/services/cameras.service'
import { systemService } from '@/services/system.service'
import type { CameraMonitoringCamera, CameraMonitoringSummary, CameraStream } from '@/types/api'

const GRID_STORAGE_KEY = 'trafficops-live-monitor-grid'
const GRID_OPTIONS = [1, 2, 4, 6, 9]

type FilterMode = 'all' | 'online' | 'offline' | 'ai'
type SortMode = 'name' | 'status' | 'location' | 'activity'

function formatTimestamp(value: string | null): string {
  if (!value) return 'No recent update'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'No recent update'
  const diffSeconds = Math.max(0, (Date.now() - date.getTime()) / 1000)
  if (diffSeconds < 60) return 'Just now'
  if (diffSeconds < 3600) return `${Math.round(diffSeconds / 60)}m ago`
  if (diffSeconds < 86400) return `${Math.round(diffSeconds / 3600)}h ago`
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function statusTone(status: string): string {
  switch (status) {
    case 'healthy':
      return 'bg-emerald-100 text-emerald-700 ring-emerald-200'
    case 'degraded':
      return 'bg-amber-100 text-amber-700 ring-amber-200'
    case 'offline':
      return 'bg-red-100 text-red-700 ring-red-200'
    default:
      return 'bg-slate-200 text-slate-700 ring-slate-200'
  }
}

function HlsVideoBox({ cameraId, cameraName, className, autoPlay = true }: {
  cameraId: number
  cameraName: string
  className?: string
  autoPlay?: boolean
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const [stream, setStream] = useState<CameraStream | null>(null)
  const [isMuted, setIsMuted] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [state, setState] = useState<'loading' | 'playing' | 'error' | 'unavailable'>('loading')

  useEffect(() => {
    let isActive = true
    void (async () => {
      try {
        const data = await systemService.cameraStream(cameraId)
        if (!isActive) return
        setStream(data)
        if (!data.available || !data.hls_url) {
          setState('unavailable')
          setError(data.reason ?? 'No stream available')
          return
        }
        setState('loading')
        setError(null)
      } catch {
        if (!isActive) return
        setState('unavailable')
        setError('Unable to load stream metadata')
      }
    })()

    return () => {
      isActive = false
    }
  }, [cameraId])

  useEffect(() => {
    if (!stream || !stream.available || !stream.hls_url || !videoRef.current) return

    let hls: any = null

    async function attach() {
      const HlsModule = await import('hls.js')
      const Hls = HlsModule.default
      if (!Hls.isSupported()) {
        if (videoRef.current && stream && videoRef.current.canPlayType('application/vnd.apple.mpegurl')) {
          videoRef.current.src = stream.hls_url!
          videoRef.current.muted = isMuted
          videoRef.current.play().catch(() => undefined)
          setState('playing')
          return
        }
        setState('error')
        setError('HLS playback is not supported in this browser.')
        return
      }

      const video = videoRef.current
      if (!video) return
      hls = new Hls({
        lowLatencyMode: true,
        backBufferLength: 10,
        maxBufferLength: 20,
        enableWorker: true,
      })

      if (stream && stream.hls_url) {
        hls.on(Hls.Events.MEDIA_ATTACHED, () => {
          hls.loadSource(stream.hls_url!)
        })
      }

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        video.muted = isMuted
        video.play().catch(() => undefined)
        setState('playing')
      })

      hls.on(Hls.Events.ERROR, (_event: unknown, data: any) => {
        if (data && data.fatal) {
          setState('error')
          setError('Stream error. The feed may be temporarily unavailable.')
        }
      })

      hls.attachMedia(video)
    }

    void attach()

    return () => {
      if (hls && typeof hls.destroy === 'function') {
        hls.destroy()
      }
      if (videoRef.current) {
        videoRef.current.pause()
      }
    }
  }, [stream, isMuted])

  useEffect(() => {
    if (!videoRef.current) return
    videoRef.current.muted = isMuted
  }, [isMuted, stream])

  const showUnavailable = state === 'unavailable' || !stream?.available

  return (
    <div className={`relative overflow-hidden rounded-xl border border-slate-200 bg-slate-950 ${className ?? ''}`}>
      {stream?.available && stream.hls_url ? (
        <video
          ref={videoRef}
          className="h-full w-full object-cover"
          muted={isMuted}
          playsInline
          autoPlay={autoPlay}
          controls={false}
        />
      ) : null}

      {showUnavailable && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/90 px-4 text-center text-slate-300">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-800 text-slate-200">
            <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.069A1 1 0 0121 8.871v6.258a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </div>
          <p className="text-sm font-semibold">Camera Offline</p>
          <p className="mt-1 text-xs text-slate-400">{error ?? 'Stream is unavailable.'}</p>
        </div>
      )}

      {state === 'loading' && stream?.available && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-950/65">
          <div className="flex items-center gap-2 rounded-full bg-slate-800/80 px-3 py-2 text-xs font-medium text-slate-200">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-400 border-t-blue-400" />
            Connecting…
          </div>
        </div>
      )}

      {state === 'error' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-red-950/80 px-4 text-center text-red-100">
          <p className="text-sm font-semibold">Stream Error</p>
          <p className="mt-1 text-xs text-red-200">{error}</p>
        </div>
      )}

      <div className="absolute left-3 top-3 flex items-center gap-2">
        <span className="rounded-full border border-emerald-500/60 bg-emerald-500/90 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em] text-white">
          {stream?.available ? 'Live' : 'Offline'}
        </span>
        {cameraName && (
          <span className="rounded-full bg-slate-950/60 px-2 py-0.5 text-[10px] font-medium text-slate-100 ring-1 ring-white/10">
            {cameraName}
          </span>
        )}
      </div>

      <div className="absolute right-3 top-3">
        <button
          type="button"
          onClick={() => setIsMuted(v => !v)}
          className="rounded-full border border-white/10 bg-slate-950/60 px-2 py-1 text-[10px] font-medium text-slate-100 hover:bg-slate-900"
        >
          {isMuted ? 'Unmute' : 'Mute'}
        </button>
      </div>
    </div>
  )
}

function CameraCard({ camera, onOpen }: { camera: CameraMonitoringCamera; onOpen: (camera: CameraMonitoringCamera) => void }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const lastUpdated = formatTimestamp(camera.last_seen ?? camera.latest_measurement_at)

  return (
    <div className="group relative overflow-hidden rounded-[14px] border border-slate-800 bg-slate-950 shadow-[0_16px_40px_rgba(2,6,23,0.45)] transition-all duration-200 hover:border-sky-500/50 hover:shadow-[0_18px_45px_rgba(14,116,144,0.18)]">
      <div className="absolute inset-0 bg-gradient-to-b from-slate-950/35 via-transparent to-slate-950/80" />

      <div className="relative h-[210px] overflow-hidden bg-slate-950">
        <HlsVideoBox cameraId={camera.id} cameraName={camera.name} className="h-full rounded-none border-none" autoPlay />

        <div className="pointer-events-none absolute inset-x-0 top-0 flex items-center justify-between px-2.5 py-2">
          <div className="flex items-center gap-1.5">
            <span className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-semibold ${camera.is_online ? 'bg-emerald-500/20 text-emerald-200 ring-1 ring-emerald-500/30' : 'bg-red-500/20 text-red-200 ring-1 ring-red-500/30'}`}>
              <span className="h-1.5 w-1.5 rounded-full bg-current" />
              {camera.is_online ? 'LIVE' : 'OFF'}
            </span>
            {camera.ai_active && (
              <span className="rounded-full bg-sky-500/20 px-1.5 py-0.5 text-[9px] font-semibold text-sky-200 ring-1 ring-sky-500/30">
                AI
              </span>
            )}
          </div>

          <div className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen(v => !v)}
              className="pointer-events-auto rounded-full border border-slate-700 bg-slate-900/80 px-1.5 py-0.5 text-[10px] text-slate-200 hover:bg-slate-800"
              aria-label="Camera options"
            >
              ⋯
            </button>
            {menuOpen && (
              <div className="absolute right-0 top-8 z-20 w-36 rounded-xl border border-slate-700 bg-slate-900 p-1 shadow-lg">
                <button type="button" onClick={() => { setMenuOpen(false); onOpen(camera) }} className="block w-full rounded-lg px-2 py-2 text-left text-xs text-slate-200 hover:bg-slate-800">View details</button>
                <button type="button" onClick={() => setMenuOpen(false)} className="block w-full rounded-lg px-2 py-2 text-left text-xs text-slate-200 hover:bg-slate-800">Refresh</button>
              </div>
            )}
          </div>
        </div>

        <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end justify-between gap-2 px-2.5 pb-2">
          <div className="min-w-0">
            <p className="truncate text-[11px] font-semibold text-white">{camera.name}</p>
            <p className="truncate text-[9px] text-slate-300">{camera.location ?? 'Unassigned location'}</p>
          </div>
          <div className="flex items-center gap-1.5 text-[9px] text-slate-200">
            <span className={`inline-flex rounded-full px-1.5 py-0.5 ring-1 ${statusTone(camera.health_status)}`}>
              {camera.health_status}
            </span>
            <span className="rounded-full bg-slate-900/80 px-1.5 py-0.5 text-slate-200 ring-1 ring-slate-700">{camera.ai_active ? `${camera.latest_vehicle_count}v` : 'idle'}</span>
          </div>
        </div>
      </div>

      <div className="relative flex items-center justify-between gap-2 border-t border-slate-800 bg-slate-950/90 px-2.5 py-2">
        <div className="min-w-0 flex-1 text-[10px] text-slate-400">
          <div className="truncate">{camera.connectivity_status}</div>
          <div className="mt-0.5 truncate">{lastUpdated}</div>
        </div>

        <button
          type="button"
          onClick={() => onOpen(camera)}
          className="rounded-md border border-sky-500/30 bg-sky-500/10 px-2 py-1 text-[10px] font-semibold text-sky-200 hover:bg-sky-500/15"
        >
          Detail
        </button>
      </div>
    </div>
  )
}

function DetailModal({ camera, onClose }: { camera: CameraMonitoringCamera | null; onClose: () => void }) {
  if (!camera) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4 py-6 backdrop-blur-sm">
      <div className="w-full max-w-5xl overflow-hidden rounded-2xl border border-slate-700 bg-slate-950 shadow-[0_30px_80px_rgba(15,23,42,0.75)]">
        <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
          <div>
            <p className="text-lg font-semibold text-slate-100">{camera.name}</p>
            <p className="text-xs text-slate-400">{camera.location ?? 'Unassigned location'}</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800">Close</button>
        </div>

        <div className="grid gap-4 p-4 md:grid-cols-[1.7fr_0.9fr]">
          <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
            <div className="h-[420px]">
              <HlsVideoBox cameraId={camera.id} cameraName={camera.name} className="h-full" autoPlay />
            </div>
          </div>

          <div className="space-y-3">
            <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.13em] text-slate-400">Status</p>
              <div className="mt-2 flex items-center justify-between">
                <span className={`inline-flex rounded-full px-2 py-1 text-[10px] font-semibold ${camera.is_online ? 'bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30' : 'bg-red-500/15 text-red-300 ring-1 ring-red-500/30'}`}>
                  {camera.is_online ? 'Online' : 'Offline'}
                </span>
                <span className={`inline-flex rounded-full px-2 py-1 text-[10px] font-semibold ring-1 ${statusTone(camera.health_status)}`}>
                  {camera.health_status}
                </span>
              </div>
              <p className="mt-3 text-xs text-slate-400">Last seen: {formatTimestamp(camera.last_seen)}</p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.13em] text-slate-400">AI activity</p>
              <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                <div className="rounded-lg border border-slate-800 bg-slate-950 p-2">
                  <p className="text-[10px] uppercase text-slate-500">Vehicles</p>
                  <p className="mt-1 font-semibold text-slate-100">{camera.latest_vehicle_count}</p>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950 p-2">
                  <p className="text-[10px] uppercase text-slate-500">AI state</p>
                  <p className="mt-1 font-semibold text-slate-100">{camera.ai_active ? 'Active' : 'Idle'}</p>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.13em] text-slate-400">Monitoring</p>
              <ul className="mt-3 space-y-2 text-xs text-slate-300">
                <li className="flex items-center justify-between"><span>HLS stream</span> <span>{camera.hls_available ? 'Available' : 'Unavailable'}</span></li>
                <li className="flex items-center justify-between"><span>Connection</span> <span>{camera.connectivity_status}</span></li>
                <li className="flex items-center justify-between"><span>AI status</span> <span>{camera.ai_active ? 'Monitoring' : 'Waiting'}</span></li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export function LiveMonitoringPage() {
  const [summary, setSummary] = useState<CameraMonitoringSummary | null>(null)
  const [layout, setLayout] = useState<number>(() => {
    const saved = Number(window.localStorage.getItem(GRID_STORAGE_KEY) ?? '4')
    return GRID_OPTIONS.includes(saved) ? saved : 4
  })
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<FilterMode>('all')
  const [sort, setSort] = useState<SortMode>('status')
  const [selectedCameraId, setSelectedCameraId] = useState<number | null>(null)

  useEffect(() => {
    window.localStorage.setItem(GRID_STORAGE_KEY, String(layout))
  }, [layout])

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const data = await cameraService.monitoringSummary()
        if (mounted) setSummary(data)
      } catch {
        if (mounted) setSummary(null)
      }
    }

    void load()
    const id = window.setInterval(() => { void load() }, 15000)
    return () => {
      mounted = false
      window.clearInterval(id)
    }
  }, [])

  const filteredCameras = useMemo(() => {
    if (!summary) return []

    let items = [...summary.cameras]

    if (search.trim()) {
      const q = search.trim().toLowerCase()
      items = items.filter(camera =>
        camera.name.toLowerCase().includes(q) ||
        (camera.location ?? '').toLowerCase().includes(q)
      )
    }

    if (filter === 'online') items = items.filter(camera => camera.is_online)
    if (filter === 'offline') items = items.filter(camera => !camera.is_online)
    if (filter === 'ai') items = items.filter(camera => camera.ai_active)

    items.sort((a, b) => {
      switch (sort) {
        case 'name':
          return a.name.localeCompare(b.name)
        case 'location':
          return (a.location ?? '').localeCompare(b.location ?? '')
        case 'activity':
          return b.latest_vehicle_count - a.latest_vehicle_count
        case 'status':
        default:
          return Number(b.is_online) - Number(a.is_online) || Number(b.ai_active) - Number(a.ai_active)
      }
    })

    return items
  }, [filter, search, sort, summary])

  const selectedCamera = summary?.cameras.find(item => item.id === selectedCameraId) ?? null

  const gridClass =
    layout === 1 ? 'grid-cols-1' :
    layout === 2 ? 'grid-cols-1 md:grid-cols-2' :
    layout === 4 ? 'grid-cols-1 md:grid-cols-2 xl:grid-cols-4' :
    layout === 6 ? 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3' :
    'grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-3'

  const cameraTree = useMemo(() => {
    const map = new Map<string, { label: string; count: number; online: number; offline: number }>()
    for (const camera of filteredCameras) {
      const key = camera.location ?? 'Unassigned'
      const current = map.get(key) ?? { label: key, count: 0, online: 0, offline: 0 }
      current.count += 1
      if (camera.is_online) current.online += 1
      else current.offline += 1
      map.set(key, current)
    }
    return Array.from(map.values())
  }, [filteredCameras])

  return (
    <div className="space-y-3 p-2 md:p-3">
      <div className="rounded-[18px] border border-slate-800 bg-slate-950/80 px-3 py-2.5 shadow-[0_18px_45px_rgba(2,6,23,0.45)]">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <div className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-sky-500/40 bg-sky-500/10 text-sky-200">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">System status</p>
              <h1 className="truncate text-lg font-semibold text-white">Live Monitoring</h1>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-[10px] text-slate-300">
            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 font-medium text-emerald-300"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Online</span>
            <span className="rounded-full border border-slate-700 bg-slate-900 px-2 py-1 font-medium">{summary?.online_cameras ?? 0} active</span>
            <span className="rounded-full border border-slate-700 bg-slate-900 px-2 py-1 font-medium">{summary?.active_ai_analyses ?? 0} AI</span>
            <span className="rounded-full border border-slate-700 bg-slate-900 px-2 py-1 font-medium">{summary?.current_detected_vehicle_count ?? 0} vehicles</span>
          </div>
        </div>
      </div>

      <div className="grid gap-3 xl:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="rounded-[18px] border border-slate-800 bg-slate-950/80 p-3 shadow-[0_18px_45px_rgba(2,6,23,0.45)]">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Sites</p>
              <h2 className="mt-1 text-sm font-semibold text-white">Camera tree</h2>
            </div>
            <span className="rounded-full border border-slate-700 bg-slate-900 px-2 py-0.5 text-[9px] font-medium text-slate-300">{filteredCameras.length}</span>
          </div>

          <label className="mb-3 block">
            <span className="sr-only">Search cameras</span>
            <input
              type="search"
              value={search}
              onChange={event => setSearch(event.target.value)}
              placeholder="Search / filter"
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500"
            />
          </label>

          <div className="space-y-2">
            {cameraTree.map(site => (
              <div key={site.label} className="rounded-xl border border-slate-800 bg-slate-900/70 p-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="inline-flex h-5 w-5 items-center justify-center rounded-md border border-slate-700 bg-slate-800 text-[9px] text-slate-300">{site.count}</span>
                    <p className="truncate text-xs font-medium text-slate-100">{site.label}</p>
                  </div>
                  <div className="flex items-center gap-1 text-[9px] text-slate-400">
                    <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />{site.online}</span>
                    <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-red-400" />{site.offline}</span>
                  </div>
                </div>

                <div className="mt-2 space-y-1.5">
                  {filteredCameras.filter(camera => (camera.location ?? 'Unassigned') === site.label).slice(0, 5).map(camera => (
                    <button
                      key={camera.id}
                      type="button"
                      onClick={() => setSelectedCameraId(camera.id)}
                      className={`flex w-full items-center justify-between rounded-lg border px-2 py-1.5 text-left text-[11px] transition ${selectedCameraId === camera.id ? 'border-sky-500/40 bg-sky-500/10 text-sky-100' : 'border-slate-700 bg-slate-950/60 text-slate-200 hover:border-slate-600'}`}
                    >
                      <span className="truncate">{camera.name}</span>
                      <span className={`inline-flex h-2 w-2 rounded-full ${camera.is_online ? 'bg-emerald-400' : 'bg-red-400'}`} />
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </aside>

        <div className="space-y-3">
          <div className="rounded-[18px] border border-slate-800 bg-slate-950/80 p-3 shadow-[0_18px_45px_rgba(2,6,23,0.4)]">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex flex-wrap items-center gap-2 text-[10px] text-slate-300">
                <span className="inline-flex items-center gap-1 rounded-full border border-slate-700 bg-slate-900 px-2 py-1 font-medium"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Live</span>
                <span className="rounded-full border border-slate-700 bg-slate-900 px-2 py-1 font-medium">{summary?.online_cameras ?? 0} online</span>
                <span className="rounded-full border border-slate-700 bg-slate-900 px-2 py-1 font-medium">{summary?.active_ai_analyses ?? 0} AI</span>
                <span className="rounded-full border border-slate-700 bg-slate-900 px-2 py-1 font-medium">{summary?.current_detected_vehicle_count ?? 0} vehicles</span>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <div className="flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-900 p-1">
                  {GRID_OPTIONS.map(option => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => setLayout(option)}
                      className={`rounded-md px-2.5 py-1 text-[10px] font-semibold ${layout === option ? 'bg-slate-100 text-slate-900' : 'text-slate-200 hover:text-white'}`}
                    >
                      {option}
                    </button>
                  ))}
                </div>

                <button type="button" className="rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-[10px] font-medium text-slate-200 hover:bg-slate-800">Fullscreen</button>
                <button type="button" className="rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-[10px] font-medium text-slate-200 hover:bg-slate-800">Pause</button>
                <button type="button" onClick={() => window.location.reload()} className="rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-[10px] font-medium text-slate-200 hover:bg-slate-800">Refresh</button>
              </div>
            </div>

            <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
              <select value={filter} onChange={event => setFilter(event.target.value as FilterMode)} className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 sm:w-32">
                <option value="all">All cameras</option>
                <option value="online">Online</option>
                <option value="offline">Offline</option>
                <option value="ai">AI Active</option>
              </select>

              <select value={sort} onChange={event => setSort(event.target.value as SortMode)} className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 sm:w-36">
                <option value="status">Status</option>
                <option value="name">Name</option>
                <option value="location">Location</option>
                <option value="activity">Detection</option>
              </select>
            </div>
          </div>

          {filteredCameras.length === 0 ? (
            <div className="rounded-[18px] border border-slate-800 bg-[radial-gradient(circle_at_top,_rgba(14,165,233,0.08),_transparent_35%),_rgba(2,6,23,0.92)] p-10 text-center shadow-[0_18px_45px_rgba(2,6,23,0.4)]">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full border border-slate-700 bg-slate-900 text-slate-300">
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M15 10l4.553-2.069A1 1 0 0121 8.871v6.258a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </div>
              <p className="text-lg font-semibold text-white">Monitoring queue ready</p>
              <p className="mt-1 text-sm text-slate-400">No live camera feeds are currently available. Cameras will appear here when they come online.</p>
            </div>
          ) : (
            <div className={`grid gap-2 ${gridClass}`}>
              {filteredCameras.map(camera => (
                <CameraCard key={camera.id} camera={camera} onOpen={item => setSelectedCameraId(item.id)} />
              ))}
            </div>
          )}
        </div>
      </div>

      <DetailModal camera={selectedCamera} onClose={() => setSelectedCameraId(null)} />
    </div>
  )
}
