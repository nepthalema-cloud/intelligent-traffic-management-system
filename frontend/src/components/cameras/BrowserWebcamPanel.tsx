/**
 * BrowserWebcamPanel — Phase 5C
 *
 * Captures the user's browser webcam via getUserMedia(), streams JPEG frames
 * over an authenticated WebSocket to the Django Channels consumer, which runs
 * YOLOv8 vehicle detection and posts measurements back to Django.
 *
 * Labels:
 *   Browser Camera testing — transient, does not create Camera records
 *
 * Architecture:
 *   Browser (getUserMedia) → canvas.toBlob(JPEG) → WS → WebcamDetectionConsumer
 *     → YOLO → TrafficMeasurement → WS push → this component
 *
 * Multi-PC: The WS URL is derived from window.location.hostname so it always
 * connects to the server, not to the browser's own localhost.
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { tokenStorage } from '@/lib/apiClient'

type PermissionState = 'idle' | 'requesting' | 'granted' | 'denied' | 'unavailable'
type SessionState    = 'inactive' | 'starting' | 'active' | 'error'

interface Detection {
  vehicle_count:    number
  avg_speed_kmh:    number | null
  measurement_id:   number | null
  interval_seconds: number
}

interface Props {
  /** Called when a new measurement is posted so the parent can refresh counts */
  onMeasurement?: (vehicleCount: number) => void
}

// ── WS URL helper ─────────────────────────────────────────────────────────
// Derives the WebSocket URL from the current page's hostname so the component
// works correctly from any PC on the LAN (not just localhost).
function buildWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host  = window.location.hostname
  // Django/Daphne always on port 8000 in dev
  const port  = import.meta.env.VITE_WS_PORT ?? '8000'
  const token = tokenStorage.getAccess() ?? ''
  return `${proto}//${host}:${port}/ws/webcam-detection/?token=${token}`
}

// Interval between captured frames (ms). 200 ms → ~5 fps to YOLO.
const FRAME_INTERVAL_MS = 200

export function BrowserWebcamPanel({ onMeasurement }: Props) {
  const videoRef    = useRef<HTMLVideoElement>(null)
  const canvasRef   = useRef<HTMLCanvasElement>(null)
  const overlayRef  = useRef<HTMLCanvasElement>(null)
  const wsRef       = useRef<WebSocket | null>(null)
  const streamRef   = useRef<MediaStream | null>(null)
  const timerRef    = useRef<ReturnType<typeof setInterval> | null>(null)

  const [permission, setPermission] = useState<PermissionState>('idle')
  const [session,    setSession]    = useState<SessionState>('inactive')
  const [lastDet,    setLastDet]    = useState<Detection | null>(null)
  const [totalVehicles, setTotalVehicles] = useState(0)
  const [sessionId,  setSessionId]  = useState<string | null>(null)
  const [errorMsg,   setErrorMsg]   = useState<string | null>(null)
  const [deviceLabel, setDeviceLabel] = useState('')
  const [annotatedSrc, setAnnotatedSrc] = useState<string | null>(null)
  const [liveDetections, setLiveDetections] = useState<any[] | null>(null)
  const [liveEvents, setLiveEvents] = useState<any[] | null>(null)

  // ── Cleanup on unmount ─────────────────────────────────────────────
  useEffect(() => {
    return () => {
      stopEverything()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Frame capture loop ─────────────────────────────────────────────
  const startFrameLoop = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      const video  = videoRef.current
      const canvas = canvasRef.current
      const ws     = wsRef.current
      if (!video || !canvas || !ws || ws.readyState !== WebSocket.OPEN) return
      if (video.readyState < 2) return  // not enough data yet

      const ctx = canvas.getContext('2d')
      if (!ctx) return
      canvas.width  = video.videoWidth  || 640
      canvas.height = video.videoHeight || 480
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

      canvas.toBlob(blob => {
        if (!blob || !ws || ws.readyState !== WebSocket.OPEN) return
        const reader = new FileReader()
        reader.onloadend = () => {
          const b64 = (reader.result as string).split(',')[1]
          ws.send(JSON.stringify({ type: 'frame', data: b64 }))
        }
        reader.readAsDataURL(blob)
      }, 'image/jpeg', 0.7)
    }, FRAME_INTERVAL_MS)
  }, [])

  // ── Stop everything cleanly ────────────────────────────────────────
  const stopEverything = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'stop' }))
      }
      wsRef.current.close()
      wsRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
    setSession('inactive')
  }, [])

  // ── Start: request permission → open WS → start frames ────────────
  const handleStart = useCallback(async () => {
    setErrorMsg(null)
    setPermission('requesting')
    setSession('starting')

    // 1. Request browser camera permission
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    } catch (err: unknown) {
      const name = (err as { name?: string }).name ?? ''
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        setPermission('denied')
      } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
        setPermission('unavailable')
        setErrorMsg('No camera found on this device.')
      } else if (name === 'NotReadableError') {
        setPermission('unavailable')
        setErrorMsg('Camera is already in use by another application.')
      } else {
        setPermission('unavailable')
        setErrorMsg(`Camera error: ${name || 'Unknown error'}`)
      }
      setSession('error')
      return
    }

    setPermission('granted')
    streamRef.current = stream

    // 2. Show local preview immediately (no server needed for this)
    if (videoRef.current) {
      videoRef.current.srcObject = stream
      void videoRef.current.play().catch(() => {})
    }

    // Capture device label for display
    const tracks = stream.getVideoTracks()
    if (tracks.length > 0) setDeviceLabel(tracks[0].label || 'Browser Camera')

    // 3. Open authenticated WebSocket to the server
    const wsUrl = buildWsUrl()
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({
        type:         'start',
        device_label: tracks[0]?.label ?? 'Browser Camera',
      }))
    }

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data as string)
        if (msg.type === 'session_started') {
          setSessionId(msg.session_id as string)
          setSession('active')
          startFrameLoop()
        } else if (msg.type === 'frame_update') {
          // Annotated JPEG frame (base64) and per-frame detection metadata
          try {
            if (msg.frame) setAnnotatedSrc(`data:image/jpeg;base64,${msg.frame}`)
            setLiveDetections(msg.detections ?? null)
            setLiveEvents(msg.events ?? null)
          } catch (e) { /* ignore */ }
        } else if (msg.type === 'detection') {
          const det: Detection = {
            vehicle_count:    msg.vehicle_count as number,
            avg_speed_kmh:    msg.avg_speed_kmh as number | null,
            measurement_id:   msg.measurement_id as number | null,
            interval_seconds: msg.interval_seconds as number,
          }
          setLastDet(det)
          setTotalVehicles(v => v + det.vehicle_count)
          onMeasurement?.(det.vehicle_count)
        } else if (msg.type === 'error') {
          setErrorMsg(msg.message as string)
          setSession('error')
          stopEverything()
        } else if (msg.type === 'session_ended') {
          stopEverything()
        }
      } catch { /* ignore malformed messages */ }
    }

    ws.onerror = () => {
      setErrorMsg('WebSocket connection failed. Is the server running?')
      setSession('error')
      stopEverything()
    }

    ws.onclose = (evt) => {
      if (evt.code !== 1000 && session !== 'inactive') {
        setSession('inactive')
      }
    }
  }, [startFrameLoop, stopEverything, onMeasurement, session])

  // Draw live detections onto overlay canvas so boxes are synchronized with
  // the local video preview even if server-annotated JPEG is delayed.
  useEffect(() => {
    const canvas = overlayRef.current
    const video = videoRef.current
    if (!canvas || !video) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const resizeAndDraw = () => {
      const rect = video.getBoundingClientRect()
      // size canvas to displayed video size (CSS pixels)
      canvas.width = Math.max(1, Math.round(rect.width))
      canvas.height = Math.max(1, Math.round(rect.height))
      canvas.style.width = `${rect.width}px`
      canvas.style.height = `${rect.height}px`

      // clear
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      const dets = liveDetections ?? []
      if (!dets || dets.length === 0) return

      for (const d of dets) {
        try {
          const bbox = d.bbox || d['bbox']
          if (!bbox || bbox.length < 4) continue
          const x1 = bbox[0] * canvas.width
          const y1 = bbox[1] * canvas.height
          const x2 = bbox[2] * canvas.width
          const y2 = bbox[3] * canvas.height
          const w = Math.max(2, x2 - x1)
          const h = Math.max(2, y2 - y1)

          // deterministic color per track id
          const tid = String(d.track_id ?? d['track_id'] ?? '')
          const color = (() => {
            let hash = 0
            for (let i = 0; i < tid.length; i++) hash = ((hash << 5) - hash) + tid.charCodeAt(i)
            const r = (hash >> 16) & 255
            const g = (hash >> 8) & 255
            const b = hash & 255
            return `rgb(${Math.abs(r)%200 + 55},${Math.abs(g)%200 + 55},${Math.abs(b)%200 + 55})`
          })()

          ctx.strokeStyle = color
          ctx.lineWidth = 2
          ctx.strokeRect(x1, y1, w, h)

          // label: ID · class · confidence · plate
          const parts = []
          if (d.track_id !== undefined) parts.push(`#${d.track_id}`)
          if (d.class) parts.push(String(d.class))
          if (d.confidence) parts.push(`${Math.round(d.confidence * 100)}%`)
          if (d.plate) parts.push(String(d.plate))
          const label = parts.join(' | ')

          if (label) {
            ctx.font = '12px Inter, Arial'
            ctx.textBaseline = 'top'
            const pad = 6
            const textW = ctx.measureText(label).width + pad * 2
            const textH = 18
            ctx.fillStyle = color
            ctx.fillRect(x1, Math.max(0, y1 - textH - 4), textW, textH)
            ctx.fillStyle = 'white'
            ctx.fillText(label, x1 + pad, Math.max(0, y1 - textH - 2))
          }
        } catch (e) {
          // ignore per-detection errors
        }
      }
    }

    // redraw when detections arrive and on resize/animation frame
    resizeAndDraw()
    const obs = new ResizeObserver(resizeAndDraw)
    obs.observe(video)
    let rafId: number | null = null
    const loop = () => {
      resizeAndDraw()
      rafId = requestAnimationFrame(loop)
    }
    rafId = requestAnimationFrame(loop)

    return () => {
      obs.disconnect()
      if (rafId !== null) cancelAnimationFrame(rafId)
    }
  }, [liveDetections, annotatedSrc, session])

  const handleStop = useCallback(() => {
    stopEverything()
    setTotalVehicles(0)
    setLastDet(null)
    setSessionId(null)
    setPermission('idle')
  }, [stopEverything])

  // ── Derived state labels ───────────────────────────────────────────
  const isActive   = session === 'active'
  const isStarting = session === 'starting'
  const canStart   = session === 'inactive' || session === 'error'

  const sessionBadge = isActive
    ? { label: 'AI PROCESSING', cls: 'bg-emerald-100 text-emerald-700 border border-emerald-200' }
    : session === 'starting'
    ? { label: 'STARTING…', cls: 'bg-amber-100 text-amber-700 border border-amber-200' }
    : { label: 'INACTIVE', cls: 'bg-slate-100 text-slate-500 border border-slate-200' }

  const isWsAvailable = typeof WebSocket !== 'undefined'
  const isCameraAvailable = typeof navigator !== 'undefined'
    && typeof navigator.mediaDevices !== 'undefined'

  return (
    <div className="card rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-50 border border-amber-200">
            <svg className="h-4 w-4 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75}
                d="M15 10l4.553-2.069A1 1 0 0121 8.871v6.258a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900">Browser Webcam Test</p>
            <p className="text-[10px] text-slate-400">TEST SOURCE — NOT LIVE CCTV</p>
          </div>
        </div>
        <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold ${sessionBadge.cls}`}>
          {sessionBadge.label}
        </span>
      </div>

      {/* Video preview */}
      <div className="relative bg-slate-900" style={{ aspectRatio: '16/9' }}>
        <video
          ref={videoRef}
          className={`w-full h-full object-cover transition-opacity duration-300 ${isActive || isStarting ? 'opacity-100' : 'opacity-0'}`}
          muted
          playsInline
          aria-label="Browser webcam live preview"
        />
        {/* Canvas used only for frame capture, not displayed */}
        <canvas ref={canvasRef} className="hidden" aria-hidden="true" />
        {/* Overlay canvas for live detection boxes (drawn client-side) */}
        <canvas ref={overlayRef} className="absolute inset-0 h-full w-full pointer-events-none" aria-hidden="true" />

        {/* Idle / error overlay */}
        {!isActive && !isStarting && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400 gap-3 px-4">
            {permission === 'denied' ? (
              <>
                <svg className="h-10 w-10 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                </svg>
                <p className="text-sm font-medium text-red-400">Camera permission denied</p>
                <p className="text-xs text-slate-500 text-center">
                  Allow camera access in your browser settings, then try again.
                </p>
              </>
            ) : permission === 'unavailable' ? (
              <>
                <svg className="h-10 w-10 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <p className="text-sm font-medium text-amber-400">Camera unavailable</p>
                <p className="text-xs text-slate-500 text-center">{errorMsg}</p>
              </>
            ) : (
              <>
                <svg className="h-10 w-10 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M15 10l4.553-2.069A1 1 0 0121 8.871v6.258a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                <p className="text-sm text-slate-500">
                  {!isCameraAvailable
                    ? 'Camera API not available in this browser'
                    : !isWsAvailable
                    ? 'WebSocket not available'
                    : 'Click "Start Webcam" to begin'}
                </p>
              </>
            )}
          </div>
        )}

        {/* Starting overlay */}
        {isStarting && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-900/70">
            <div className="flex flex-col items-center gap-2 text-white">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              <p className="text-xs">Connecting…</p>
            </div>
          </div>
        )}

        {/* Active HUD badges */}
        {isActive && (
          <>
            <div className="absolute top-2 left-2 flex items-center gap-1.5 rounded-md bg-black/60 px-2 py-1">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
              <span className="text-[10px] font-bold text-white">BROWSER WEBCAM (TEMP)</span>
            </div>
            <div className="absolute top-2 right-2 rounded-md bg-amber-600/80 px-2 py-0.5">
              <span className="text-[10px] font-bold text-white">TEST SOURCE</span>
            </div>
            {deviceLabel && (
              <div className="absolute bottom-2 left-2 rounded-md bg-black/50 px-2 py-0.5">
                <span className="text-[10px] text-slate-300 truncate max-w-[200px] block">{deviceLabel}</span>
              </div>
            )}
            {/* Annotated overlay (server-rendered) - fallback */}
            {annotatedSrc && (
              <img src={annotatedSrc} alt="Annotated" className="absolute inset-0 h-full w-full object-cover pointer-events-none" />
            )}
          </>
        )}
      </div>

      {/* Stats panel */}
      {isActive && (
        <div className="px-4 py-3 bg-slate-50 border-t border-slate-100 grid grid-cols-2 gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Vehicles (session)</p>
            <p className="text-xl font-bold text-slate-900">{totalVehicles}</p>
          </div>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Last interval</p>
            {lastDet ? (
              <p className="text-xl font-bold text-slate-900">
                {lastDet.vehicle_count}
                <span className="text-xs font-normal text-slate-400 ml-1">
                  vehicles / {lastDet.interval_seconds}s
                </span>
              </p>
            ) : (
              <p className="text-sm text-slate-400">Waiting for first detection…</p>
            )}
          </div>
          <div className="col-span-2">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Speed</p>
            <p className="text-sm text-slate-500 italic">
              NULL — no camera calibration (expected)
            </p>
          </div>
          {sessionId && (
            <div className="col-span-2">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Session</p>
              <p className="font-mono text-[10px] text-slate-400 truncate">{sessionId}</p>
            </div>
          )}
          {/* Live events list */}
          {liveEvents && liveEvents.length > 0 && (
            <div className="col-span-2">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Events</p>
              <div className="flex flex-wrap gap-2 mt-2">
                {liveEvents.map((ev, idx) => (
                  <div key={idx} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-700">{ev.type}{ev.track_id ? ` · ${ev.track_id}` : ''}{ev.plate ? ` · ${ev.plate}` : ''}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error message */}
      {errorMsg && session === 'error' && (
        <div className="px-4 py-2 bg-red-50 border-t border-red-100">
          <p className="text-xs text-red-600">{errorMsg}</p>
        </div>
      )}

      {/* Controls */}
      <div className="px-4 py-3 border-t border-slate-100 flex gap-2">
        {canStart ? (
          <button
            type="button"
            disabled={!isCameraAvailable || !isWsAvailable}
            onClick={handleStart}
            className="flex-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white
                       hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
          >
            {permission === 'denied' ? 'Retry (check browser settings)' : 'Start My Webcam'}
          </button>
        ) : (
          <button
            type="button"
            onClick={handleStop}
            className="flex-1 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold
                       text-slate-700 hover:bg-slate-50 transition-colors shadow-sm"
          >
            Stop Webcam
          </button>
        )}
      </div>

      {/* Disclaimer */}
      <div className="px-4 pb-3">
        <p className="text-[10px] text-slate-400">
          Your webcam feed is sent directly to this server for AI vehicle detection.
          Frames are not recorded or stored. Speed is always NULL (no calibration).
          This is a test source — not a physical CCTV camera.
        </p>
      </div>
    </div>
  )
}
