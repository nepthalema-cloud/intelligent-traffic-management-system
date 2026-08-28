import { useEffect, useState, useCallback } from 'react'
import { cameraService, sensorService } from '@/services/cameras.service'
import type {
  Camera, CameraHealth, Sensor, SensorHealth,
  CameraConnectionStatus,
} from '@/types/api'
import { ROLES } from '@/types/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { StatusBadge } from '@/components/ui/StatusBadge'
// CameraStreamPlayer removed — legacy live stream viewer
import { CameraConnectionBadge } from '@/components/cameras/CameraConnectionBadge'
import { BrowserWebcamPanel } from '@/components/cameras/BrowserWebcamPanel'
import { UploadVideoPanel } from '@/components/cameras/UploadVideoPanel'
import { AddCameraModal } from '@/components/cameras/AddCameraModal'
import { useAuthStore } from '@/store/authStore'
import { formatRelative } from '@/utils/time'

const WRITE_ROLES = [ROLES.SYSTEM_ADMIN, ROLES.CAMERA_TECHNICIAN]

// Test-video source detection — clearly labelled, never presented as live CCTV
function isTestSource(cam: Camera): boolean {
  return (
    cam.description.startsWith('TEST') ||
    cam.description.startsWith('LIVE-WEBCAM') ||
    cam.stream_url.includes('test-camera') ||
    cam.stream_url.includes('live-webcam')
  )
}

function SourceLabel({ cam }: { cam: Camera }) {
  if (cam.stream_url.includes('live-webcam')) {
    return <span className="rounded-full bg-amber-100 text-amber-700 px-2 py-0.5 text-[10px] font-semibold">LIVE WEBCAM</span>
  }
  if (isTestSource(cam)) {
    return <span className="rounded-full bg-slate-200 text-slate-600 px-2 py-0.5 text-[10px] font-semibold">TEST VIDEO</span>
  }
  return <span className="rounded-full bg-blue-100 text-blue-700 px-2 py-0.5 text-[10px] font-semibold">CCTV</span>
}

function CameraCard({ cam, canWrite }: { cam: Camera; canWrite: boolean }) {
  const [health,     setHealth]     = useState<CameraHealth | null>(null)
  const [connStatus, setConnStatus] = useState<CameraConnectionStatus | null>(null)
  // NOTE: Removed 'View Stream' feature — legacy live stream viewer removed.
  const [testing,    setTesting]    = useState(false)

  useEffect(() => {
    cameraService.health(cam.id).then(setHealth).catch(() => setHealth(null))
  }, [cam.id])

  async function runTest() {
    setTesting(true)
    try {
      const result = await cameraService.test(cam.id)
      setConnStatus(result)
      // Refresh health after test
      cameraService.health(cam.id).then(setHealth).catch(() => null)
    } catch {
      setConnStatus({
        state: 'rtsp_unreachable', state_label: 'Test Failed',
        colour: 'red', detail: 'Could not run test.',
        checked_at: new Date().toISOString(),
      })
    } finally { setTesting(false) }
  }

  const borderCls = health?.health_status === 'offline'  ? 'border-red-200' :
                    health?.health_status === 'degraded' ? 'border-amber-200' :
                    connStatus?.state === 'live'         ? 'border-emerald-200' :
                    'border-slate-200'

  return (
    <div className={`card rounded-xl p-4 ${borderCls}`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-semibold text-slate-900 truncate">{cam.name}</p>
            <SourceLabel cam={cam} />
          </div>
          <p className="text-xs text-slate-500 mt-0.5 capitalize">{cam.camera_type.replace('_', ' ')}</p>
        </div>
        <StatusBadge status={cam.is_active ? 'active' : 'inactive'} />
      </div>

      {/* Location */}
      <p className="text-xs text-slate-500 truncate mb-2">
        📍 {cam.intersection_name ?? cam.segment_name ?? 'No location assigned'}
      </p>
      {cam.ip_address && <p className="text-xs font-mono text-slate-400 mb-1">{cam.ip_address}</p>}
      {cam.model && <p className="text-xs text-slate-400 mb-2">{cam.model}</p>}

      {/* Connection status */}
      {connStatus && (
        <div className="mb-3">
          <CameraConnectionBadge status={connStatus} showDetail />
        </div>
      )}

      {/* Health */}
      <div className="border-t border-slate-100 pt-2 mt-2 space-y-1.5">
        {health ? (
          <>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Health</span>
              <StatusBadge status={health.health_status} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Connectivity</span>
              <span className={`text-xs font-medium ${
                health.connectivity_status === 'connected' ? 'text-emerald-600' :
                health.connectivity_status === 'disconnected' ? 'text-red-500' : 'text-slate-500'
              }`}>{health.connectivity_status}</span>
            </div>
            {health.last_seen && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Last seen</span>
                <span className="text-xs text-slate-600">{formatRelative(health.last_seen)}</span>
              </div>
            )}
          </>
        ) : (
          <p className="text-xs text-slate-400 italic">No health data</p>
        )}
      </div>

      {/* Actions */}
      <div className="mt-3 flex gap-2">
        {canWrite && (
          <button type="button" onClick={runTest} disabled={testing}
            className="flex-1 rounded-lg border border-slate-300 bg-white py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 transition-colors">
            {testing ? 'Testing…' : '▶ Test Connection'}
          </button>
        )}
        {/* Stream viewing removed — browser webcam testing remains via BrowserWebcamPanel */}
      </div>
      
    </div>
  )
}

function SensorCard({ sen }: { sen: Sensor }) {
  const [health, setHealth] = useState<SensorHealth | null>(null)
  useEffect(() => {
    sensorService.health(sen.id).then(setHealth).catch(() => setHealth(null))
  }, [sen.id])

  return (
    <div className="card rounded-xl p-4">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">{sen.name}</p>
          <p className="text-xs text-slate-500 mt-0.5 capitalize">{sen.sensor_type.replace('_', ' ')}</p>
        </div>
        <StatusBadge status={sen.is_active ? 'active' : 'inactive'} />
      </div>
      <p className="text-xs text-slate-500 truncate mb-2">
        📍 {sen.intersection_name ?? sen.segment_name ?? 'No location assigned'}
      </p>
      {sen.model && <p className="text-xs text-slate-400 mb-2">{sen.model}</p>}
      <div className="border-t border-slate-100 pt-2 mt-2 space-y-1.5">
        {health ? (
          <>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Health</span>
              <StatusBadge status={health.health_status} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Connectivity</span>
              <span className={`text-xs font-medium ${
                health.connectivity_status === 'connected' ? 'text-emerald-600' :
                health.connectivity_status === 'disconnected' ? 'text-red-500' : 'text-slate-500'
              }`}>{health.connectivity_status}</span>
            </div>
            {health.last_seen && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Last seen</span>
                <span className="text-xs text-slate-600">{formatRelative(health.last_seen)}</span>
              </div>
            )}
          </>
        ) : <p className="text-xs text-slate-400 italic">No health data</p>}
      </div>
    </div>
  )
}

type Tab = 'cameras' | 'sensors'

export function CamerasPage() {
  const { hasAnyRole } = useAuthStore()
  const canWrite = hasAnyRole(WRITE_ROLES)

  const [tab,     setTab]     = useState<Tab>('cameras')
  const [cameras, setCameras] = useState<Camera[]>([])
  const [sensors, setSensors] = useState<Sensor[]>([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [webcamVehicles, setWebcamVehicles] = useState(0)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [c, s] = await Promise.allSettled([
        cameraService.list({ page_size: 50 }),
        sensorService.list({ page_size: 50 }),
      ])
      if (c.status === 'fulfilled') setCameras(c.value.results)
      if (s.status === 'fulfilled') setSensors(s.value.results)
      if (c.status === 'rejected' && s.status === 'rejected')
        setError('Could not load camera/sensor data.')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { void load() }, [load])

  // Separate physical CCTV from registered test/webcam sources
  const realCameras    = cameras.filter(c => !isTestSource(c))
  const testCameras    = cameras.filter(c => isTestSource(c) && !c.stream_url.includes('live-webcam'))
  const webcamCameras  = cameras.filter(c => c.stream_url.includes('live-webcam'))

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Cameras &amp; Sensors</h1>
          <p className="text-sm text-slate-500">
            {cameras.length} cameras · {sensors.length} sensors
            {realCameras.length > 0 && ` · ${realCameras.length} CCTV`}
            {testCameras.length > 0 && ` · ${testCameras.length} test video`}
            {webcamCameras.length > 0 && ` · ${webcamCameras.length} webcam`}
          </p>
        </div>
        {canWrite && (
          <button type="button" onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold
                       text-white hover:bg-blue-700 shadow-sm transition-colors">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add CCTV Camera
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg border border-slate-200 bg-slate-100 p-1 w-fit">
        {(['cameras', 'sensors'] as Tab[]).map(t => (
          <button key={t} type="button" onClick={() => setTab(t)}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
              tab === t ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}>
            {t === 'cameras' ? '📷 Cameras' : '📡 Sensors'}
          </button>
        ))}
      </div>

      {loading && <LoadingSpinner />}
      {!loading && error && <ErrorMessage message={error} onRetry={load} />}

      {/* ── Cameras tab ──────────────────────────────────────────── */}
      {!loading && !error && tab === 'cameras' && (
        <div className="space-y-8">

          {/* ① Physical CCTV Cameras */}
          <section>
            <div className="flex items-center gap-2 mb-3">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Physical CCTV Cameras
              </h2>
              <span className="rounded-full bg-blue-100 text-blue-700 px-2 py-0.5 text-[10px] font-semibold border border-blue-200">
                CCTV
              </span>
            </div>
            {realCameras.length === 0 ? (
              <div className="card rounded-xl p-6 text-center">
                <p className="text-sm font-medium text-slate-700">No physical CCTV cameras registered</p>
                <p className="text-xs text-slate-400 mt-1">
                  {canWrite
                    ? 'Click "Add CCTV Camera" to onboard an IP camera with an RTSP stream.'
                    : 'No CCTV cameras have been configured yet.'}
                </p>
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {realCameras.map(cam => <CameraCard key={cam.id} cam={cam} canWrite={canWrite} />)}
              </div>
            )}
          </section>

          {/* ② Test Video Sources */}
          {(testCameras.length > 0 || webcamCameras.length > 0) && (
            <section>
              <div className="flex items-center gap-2 mb-1">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Registered Test Sources
                </h2>
                <span className="rounded-full bg-amber-100 text-amber-700 px-2 py-0.5 text-[10px] font-semibold border border-amber-200">
                  NOT LIVE CCTV
                </span>
              </div>
              <p className="text-xs text-slate-400 mb-3">
                Prerecorded MP4 test streams and webcam sources used to validate the AI detection
                pipeline. Clearly labelled and never presented as physical CCTV footage.
              </p>
              {testCameras.length > 0 && (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 mb-4">
                  {testCameras.map(cam => <CameraCard key={cam.id} cam={cam} canWrite={canWrite} />)}
                </div>
              )}
              {webcamCameras.length > 0 && (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {webcamCameras.map(cam => <CameraCard key={cam.id} cam={cam} canWrite={canWrite} />)}
                </div>
              )}
            </section>
          )}

          {/* ③ Browser Webcam Testing */}
          <section>
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Browser Webcam Testing
              </h2>
              <span className="rounded-full bg-amber-100 text-amber-700 px-2 py-0.5 text-[10px] font-semibold border border-amber-200">
                TEST SOURCE — NOT CCTV
              </span>
            </div>
            <p className="text-xs text-slate-400 mb-3">
              Capture your browser's camera directly for AI vehicle detection testing.
              Works from any PC — your webcam feed goes to this server (not localhost).
              Hold a phone with a traffic video in front of your webcam to simulate
              vehicle detection. Speed is always NULL (no calibration).
            </p>
            {webcamVehicles > 0 && (
              <div className="mb-3 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-xs font-medium text-emerald-700">
                  AI active — {webcamVehicles} vehicles detected this session
                </span>
              </div>
            )}
            <div className="max-w-sm">
              <BrowserWebcamPanel onMeasurement={count => setWebcamVehicles(v => v + count)} />
            </div>
          </section>

          {/* ④ Upload Video Analysis (ephemeral) */}
          <section>
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Upload Video Analysis
              </h2>
              <span className="rounded-full bg-slate-200 text-slate-600 px-2 py-0.5 text-[10px] font-semibold border border-slate-300">
                DEMO / TEMPORARY
              </span>
            </div>
            <p className="text-xs text-slate-400 mb-3">
              Upload a prerecorded video file and run a temporary AI analysis. Results and annotated
              video are available for download; no persistent camera record is created.
            </p>
            <div className="max-w-md">
              <UploadVideoPanel />
            </div>
          </section>

          {cameras.length === 0 && !loading && (
            <EmptyState icon="📷" title="No cameras configured"
              subtitle={canWrite
                ? 'Click "Add CCTV Camera" to onboard your first physical camera, or use the Browser Webcam below.'
                : 'No cameras have been configured yet.'} />
          )}
        </div>
      )}

      {/* ── Sensors tab ──────────────────────────────────────────── */}
      {!loading && !error && tab === 'sensors' && (
        sensors.length === 0
          ? <EmptyState icon="📡" title="No sensors configured" />
          : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {sensors.map(sen => <SensorCard key={sen.id} sen={sen} />)}
            </div>
          )
      )}

      <AddCameraModal
        open={showAdd}
        onClose={() => setShowAdd(false)}
        onCreated={() => { void load() }}
      />
    </div>
  )
}
