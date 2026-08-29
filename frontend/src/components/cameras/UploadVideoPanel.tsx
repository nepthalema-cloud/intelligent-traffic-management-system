import { useState, useEffect, useRef } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts'
import { uploadVideo, checkJobStatus, downloadResults, createAuthenticatedMediaUrl, getAnnotatedStreamUrl, discardAnalysis, rememberVideoAnalysisJob } from '@/services/uploadVideo.service'

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="w-full bg-slate-100 rounded overflow-hidden h-3">
      <div className="bg-emerald-500 h-3 transition-all duration-300" style={{ width: `${Math.min(100, pct)}%` }} />
    </div>
  )
}

function formatDuration(seconds: number) {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}s`
}

function eventColor(type: string) {
  switch (type) {
    case 'vehicle_entered': return 'bg-emerald-500'
    case 'vehicle_exited': return 'bg-slate-500'
    case 'plate': return 'bg-sky-500'
    case 'speed': return 'bg-orange-500'
    case 'violation': return 'bg-red-500'
    default: return 'bg-slate-400'
  }
}

function eventLabel(type: string) {
  switch (type) {
    case 'vehicle_entered': return 'Vehicle entered'
    case 'vehicle_exited': return 'Vehicle exited'
    case 'plate': return 'Plate recognized'
    case 'speed': return 'Speed event'
    case 'violation': return 'Violation'
    default: return 'Event'
  }
}

function VirtualList({ items, itemHeight, containerHeight, renderItem }: { items:any[]; itemHeight:number; containerHeight:number; renderItem:(item:any, index:number)=>any }) {
  const [scrollTop, setScrollTop] = useState(0)
  const visibleCount = Math.ceil(containerHeight / itemHeight)
  const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - 2)
  const endIndex = Math.min(items.length, startIndex + visibleCount + 4)
  const topSpacer = startIndex * itemHeight
  const visibleItems = items.slice(startIndex, endIndex)
  return (
    <div className="overflow-auto" style={{ height: containerHeight }} onScroll={e => setScrollTop((e.target as HTMLDivElement).scrollTop)}>
      <div style={{ height: topSpacer }} />
      {visibleItems.map((item, idx) => renderItem(item, startIndex + idx))}
      <div style={{ height: Math.max(0, (items.length - endIndex) * itemHeight) }} />
    </div>
  )
}

function Timeline({ duration, events, onSeek }: { duration: number | null, events?: any[], onSeek: (t:number)=>void }) {
  if (!duration || !events?.length) return <div className="text-xs text-slate-500">Timeline unavailable</div>
  return (
    <div className="rounded-3xl border border-slate-200 bg-slate-50 p-3">
      <div className="h-14 relative rounded-2xl bg-white shadow-sm">
        {events.map((event, index) => {
          const left = Math.min(100, (event.time / duration) * 100)
          return (
            <button key={index} type="button" title={`${eventLabel(event.type)} · ${event.time.toFixed(2)}s`} onClick={() => onSeek(event.time)}
              className={`absolute top-1/2 h-7 w-7 -translate-y-1/2 rounded-full border border-white shadow-sm ${eventColor(event.type)} transition hover:scale-110`} style={{ left: `${left}%`, transform: 'translate(-50%, -50%)' }}>
              <span className="sr-only">{eventLabel(event.type)} at {event.time.toFixed(2)}s</span>
            </button>
          )
        })}
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-[10px] text-slate-500">
        {['vehicle_entered','plate','speed','violation'].map(type => (
          <div key={type} className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-2 py-1">
            <span className={`inline-block h-2.5 w-2.5 rounded-full ${eventColor(type)}`}></span>
            <span>{eventLabel(type)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function DashboardCards({ uniqueVehicles, totalDetections, vehicleTypeCounts, averageSpeed, highestSpeed, recognizedPlates, violationCount }: { uniqueVehicles:number, totalDetections:number, vehicleTypeCounts: Record<string, number>, averageSpeed:number, highestSpeed:number, recognizedPlates:number, violationCount:number }) {
  return (
    <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-4">
      <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Unique Vehicles</div>
        <div className="mt-2 text-3xl font-semibold text-slate-900">{uniqueVehicles}</div>
      </div>
      <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Total Detections</div>
        <div className="mt-2 text-3xl font-semibold text-slate-900">{totalDetections}</div>
      </div>
      <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Average Speed</div>
        <div className="mt-2 text-3xl font-semibold text-slate-900">{averageSpeed ? `${averageSpeed.toFixed(0)} km/h` : 'N/A'}</div>
      </div>
      <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Highest Speed</div>
        <div className="mt-2 text-3xl font-semibold text-slate-900">{highestSpeed ? `${highestSpeed.toFixed(0)} km/h` : 'N/A'}</div>
      </div>
      <div className="xl:col-span-2 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Vehicle type breakdown</div>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {Object.entries(vehicleTypeCounts).map(([type, count]) => (
            <div key={type} className="rounded-2xl bg-slate-50 p-3 text-sm text-slate-600">
              <div className="font-semibold text-slate-900">{type}</div>
              <div>{count} vehicles</div>
            </div>
          ))}
        </div>
      </div>
      <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Recognized Plates</div>
        <div className="mt-2 text-3xl font-semibold text-slate-900">{recognizedPlates}</div>
      </div>
      <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Violations</div>
        <div className="mt-2 text-3xl font-semibold text-slate-900">{violationCount}</div>
      </div>
    </div>
  )
}

function ReviewTabs({ activeTab, setActiveTab }: { activeTab: string, setActiveTab: (tab:string)=>void }) {
  const tabs = [
    { key: 'review', label: 'Review' },
    { key: 'violations', label: 'Violations' },
    { key: 'snapshots', label: 'Snapshots' },
    { key: 'metadata', label: 'AI Metadata' },
  ]
  return (
    <div className="flex flex-wrap gap-2">
      {tabs.map(tab => (
        <button key={tab.key} onClick={() => setActiveTab(tab.key)}
          className={`rounded-full px-3 py-1 text-sm transition ${activeTab === tab.key ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}>
          {tab.label}
        </button>
      ))}
    </div>
  )
}

function VehicleCard({ vehicle, isSelected, onSelect, isCalibrated, plateConfidenceThreshold, imageSrc }: { vehicle:any, isSelected:boolean, onSelect:(id:string|number)=>void, isCalibrated:boolean, plateConfidenceThreshold:number, imageSrc?: string | null }) {
  const displayPlate = ((vehicle.plate_confidence ?? 0) >= plateConfidenceThreshold && vehicle.plate)
    ? vehicle.plate
    : 'Not confidently detected'
  const speedText = vehicle.avg_speed != null
    ? `${vehicle.avg_speed.toFixed(0)} km/h`
    : (isCalibrated ? 'N/A' : 'Speed unavailable (Camera not calibrated)')
  const dominantColor = vehicle.dominant_color ? vehicle.dominant_color : null

  return (
    <button onClick={() => onSelect(vehicle.track_id)}
      className={`group relative text-left rounded-2xl border p-3 transition ${isSelected ? 'border-blue-500 bg-blue-50 shadow-sm' : 'border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm'}`}>
      <div className="flex gap-3">
        <div className="h-20 w-32 overflow-hidden rounded-xl bg-slate-100">
          {vehicle.thumbnail ? <img src={imageSrc ?? vehicle.thumbnail} alt={`Track ${vehicle.track_id}`} className="h-full w-full object-cover" /> : <div className="flex h-full items-center justify-center text-xs text-slate-400">No image</div>}
        </div>
        <div className="flex-1">
          <div className="text-sm font-semibold text-slate-800">ID {vehicle.track_id}</div>
          <div className="text-xs text-slate-500">Type: {vehicle.vehicle_type ?? 'Unknown'}</div>
          <div className="mt-2 grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
            <div>Confidence: {vehicle.confidence_history?.slice(-1)[0] ? `${Math.round(vehicle.confidence_history.slice(-1)[0]*100)}%` : 'N/A'}</div>
            <div>Speed: {speedText}</div>
            <div>Plate: {displayPlate}</div>
            <div>Color: {dominantColor ? <span className="inline-flex items-center gap-2"><span className="h-3 w-3 rounded-full" style={{ backgroundColor: dominantColor }}></span>{dominantColor}</span> : 'Unknown'}</div>
          </div>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500">
        <div>First: {vehicle.first_seen?.toFixed(2)}s</div>
        <div>Last: {vehicle.last_seen?.toFixed(2)}s</div>
        <div>Duration: {vehicle.duration_seconds ? `${vehicle.duration_seconds.toFixed(2)}s` : 'N/A'}</div>
        <div>Violations: {vehicle.violation ? vehicle.violation_reasons?.join(', ') : 'None'}</div>
      </div>
    </button>
  )
}

function SnapshotGallery({ snapshots, onSeek, imageUrls }: { snapshots?: any[], onSeek:(t:number)=>void, imageUrls?: Record<string, string> }) {
  if (!snapshots || snapshots.length === 0) return <div className="text-xs text-slate-500">No notable frames saved.</div>
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {snapshots.map((snap, idx) => {
        const imageSrc = snap.image_url ? imageUrls?.[snap.image_url] ?? snap.image_url : undefined
        return (
          <button key={idx} className="group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:shadow-md" onClick={() => onSeek(snap.time)}>
            <div className="h-28 overflow-hidden bg-slate-100">
              {imageSrc ? <img src={imageSrc} alt={snap.type} className="h-full w-full object-cover" /> : <div className="flex h-full items-center justify-center text-xs text-slate-400">No image</div>}
            </div>
          <div className="p-3 text-left text-xs text-slate-600">
            <div className="font-semibold text-slate-900">{snap.type.replace('_', ' ').toUpperCase()}</div>
            <div>Time: {snap.time.toFixed(2)}s</div>
            <div>Track: {snap.track_id}</div>
            </div>
          </button>
        )
      })}
    </div>
  )
}

function MetadataPanel({ metadata }: { metadata?: any }) {
  if (!metadata) return <div className="text-xs text-slate-500">No metadata available.</div>
  return (
    <div className="grid gap-3 text-xs">
      {Object.entries(metadata).map(([key, value]) => (
        <div key={key} className="rounded-2xl border border-slate-200 bg-white p-3">
          <div className="text-slate-500 uppercase tracking-wide text-[10px]">{key.replace(/_/g,' ')}</div>
          <div className="mt-1 text-sm font-semibold text-slate-900">{typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)}</div>
        </div>
      ))}
    </div>
  )
}

function TrackingHistoryPanel({ vehicle, onStep, currentTime }: { vehicle:any, onStep:(t:number)=>void, currentTime:()=>number }) {
  if (!vehicle) return <div className="text-xs text-slate-500">Select a vehicle to inspect its track.</div>
  const frameCount = vehicle.frames?.length ?? 0
  const currentTs = currentTime()
  const idx = vehicle.frames?.findIndex((t:number)=>Math.abs(t-currentTs) < 0.5) ?? -1
  return (
    <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-sm font-semibold text-slate-800">Track history</div>
      <div className="grid grid-cols-2 gap-2 text-xs text-slate-500">
        <div>Entry: {vehicle.first_seen?.toFixed(2)}s</div>
        <div>Exit: {vehicle.last_seen?.toFixed(2)}s</div>
        <div>Avg speed: {vehicle.avg_speed ? `${vehicle.avg_speed.toFixed(0)} km/h` : 'Unavailable'}</div>
        <div>Max speed: {vehicle.max_speed ? `${vehicle.max_speed.toFixed(0)} km/h` : 'Unavailable'}</div>
      </div>
      <div className="flex items-center gap-2 pt-2">
        <button onClick={() => onStep(vehicle.frames?.[Math.max(0, (idx <= 0 ? 0 : idx - 1))] ?? vehicle.first_seen)}
          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">Prev</button>
        <button onClick={() => onStep(vehicle.frames?.[Math.min(frameCount - 1, idx + 1)] ?? vehicle.last_seen)}
          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">Next</button>
        <div className="ml-auto text-xs text-slate-500">Frame {idx+1}/{frameCount}</div>
      </div>
      <div className="rounded-2xl border border-slate-100 bg-slate-50 p-3 text-xs text-slate-600">
        Confidence history: {vehicle.confidence_history?.slice(-5).map((c:number)=>`${Math.round(c*100)}%`).join(', ') || 'N/A'}
      </div>
    </div>
  )
}

export function UploadVideoPanel() {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [result, setResult] = useState<any | null>(null)
  const [downloadData, setDownloadData] = useState<any | null>(null)
  const [progressPct, setProgressPct] = useState(0)
  const [activeTab, setActiveTab] = useState('review')
  void activeTab
  const [selectedVehicleId, setSelectedVehicleId] = useState<string | number | null>(null)
  const [vehicleFilter, setVehicleFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [duration, setDuration] = useState<number | null>(null)
  const [showDevTools, setShowDevTools] = useState(false)
  const [fallbackFrameIndex, setFallbackFrameIndex] = useState(0)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [imageUrls, setImageUrls] = useState<Record<string, string>>({})
  const [mediaLoaded, setMediaLoaded] = useState(false)
  const isAnalyzing = Boolean(uploading || (jobId && status && status !== 'done' && status !== 'failed'))
  const lastAutoSelectedVehicle = useRef<string | null>(null)
  const videoObjectUrlRef = useRef<string | null>(null)
  const lastResolvedVideoUrlRef = useRef<string | null>(null)
  const videoUrlRef = useRef<string | null>(null)
  const imageObjectUrlsRef = useRef<Record<string, string>>({})
  const statusRef = useRef<string | null>(null)
  const resultRef = useRef<any | null>(null)
  const progressRef = useRef<number>(0)

  const results = downloadData?.full_results ?? downloadData?.result
  const vehicles = results?.vehicles ?? []
  const violations = results?.violations ?? []
  const snapshots = results?.snapshots ?? []
  void snapshots
  const metadata = results?.ai_metadata ?? {}
  void metadata
  const isCalibrated = results?.ai_metadata?.speed_calibrated ?? false
  const plateConfidenceThreshold = results?.ai_metadata?.ocr_confidence_threshold ?? 0.7
  const uniqueVehicles = vehicles.length
  const totalDetections = (results?.frames ?? []).reduce((sum:number, frame:any) => sum + ((frame.detections?.length ?? 0)), 0)
  const vehicleTypeCounts = vehicles.reduce((acc: Record<string, number>, vehicle:any) => {
    acc[vehicle.vehicle_type ?? 'unknown'] = (acc[vehicle.vehicle_type ?? 'unknown'] ?? 0) + 1
    return acc
  }, {})
  const averageSpeed = vehicles.filter((v:any) => v.avg_speed != null).reduce((sum:number, v:any) => sum + (v.avg_speed ?? 0), 0) / Math.max(1, vehicles.filter((v:any) => v.avg_speed != null).length)
  const highestSpeed = Math.max(0, ...vehicles.map((v:any) => v.max_speed ?? 0))
  const recognizedPlates = vehicles.filter((v:any) => (v.plate_confidence ?? 0) >= plateConfidenceThreshold).length
  const violationCount = vehicles.filter((v:any) => v.violation).length
  const timelineEvents = results?.summary?.events?.length ? results.summary.events : vehicles.flatMap((vehicle:any) => [
    ...(vehicle.first_seen != null ? [{ type: 'vehicle_entered', time: vehicle.first_seen, track_id: vehicle.track_id }] : []),
    ...(vehicle.last_seen != null ? [{ type: 'vehicle_exited', time: vehicle.last_seen, track_id: vehicle.track_id }] : []),
  ])
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [playbackRate] = useState(1)
  const [volume] = useState(0.8)
  const [frameWidth, frameHeight] = (() => {
    const [w, h] = ((results?.resolution ?? '').split('x').map(Number))
    return [Number.isFinite(w) ? w : 1280, Number.isFinite(h) ? h : 720]
  })()

  function renderFallbackPreview() {
    const c = canvasRef.current
    const full = downloadData?.full_results ?? downloadData?.result
    if (!c || !full || !full.frames?.length) return

    const frame = full.frames[fallbackFrameIndex] ?? full.frames[0]
    const width = frameWidth || 1280
    const height = frameHeight || 720
    c.width = width
    c.height = height
    c.style.width = '100%'
    c.style.height = 'auto'

    const ctx = c.getContext('2d')
    if (!ctx) return
    ctx.clearRect(0, 0, width, height)
    ctx.fillStyle = '#0f172a'
    ctx.fillRect(0, 0, width, height)

    const detections = frame.detections || []
    detections.forEach((det:any) => {
      const x1 = det.bbox[0] * width
      const y1 = det.bbox[1] * height
      const x2 = det.bbox[2] * width
      const y2 = det.bbox[3] * height
      const w = Math.max(2, x2 - x1)
      const h = Math.max(2, y2 - y1)
      ctx.strokeStyle = '#38bdf8'
      ctx.lineWidth = 3
      ctx.strokeRect(x1, y1, w, h)
      const labelParts = [det.class, det.plate, det.confidence ? `${Math.round(det.confidence*100)}%` : null, det.speed_kmh ? `${Math.round(det.speed_kmh)} km/h` : null].filter(Boolean)
      const label = labelParts.join(' | ')
      if (label) {
        ctx.fillStyle = '#0f172a'
        ctx.fillRect(x1, Math.max(0, y1 - 22), ctx.measureText(label).width + 14, 20)
        ctx.fillStyle = '#ffffff'
        ctx.font = '12px Arial'
        ctx.fillText(label, x1 + 6, Math.max(12, y1 - 8))
      }
    })
    ctx.fillStyle = '#ffffff'
    ctx.font = '12px Arial'
    ctx.fillText(`Fallback frame ${fallbackFrameIndex + 1} / ${full.frames.length}`, 12, height - 12)
  }

  useEffect(() => {
    statusRef.current = status
  }, [status])

  useEffect(() => {
    resultRef.current = result
  }, [result])

  useEffect(() => {
    progressRef.current = progressPct
  }, [progressPct])

  useEffect(() => {
    videoUrlRef.current = videoUrl
  }, [videoUrl])

  useEffect(() => {
    if (!downloadData?.annotated_video) renderFallbackPreview()
  }, [downloadData, fallbackFrameIndex])

  // Poll job status while a jobId is active. Polling is started once per jobId
  // to avoid re-creating intervals when `status` changes frequently.
  useEffect(() => {
    if (!jobId) return

    let mounted = true
    let intervalId: number | undefined
    const downloadedRef = { done: false }

    const stopPolling = () => {
      if (intervalId) window.clearInterval(intervalId)
      intervalId = undefined
    }

    const pollOnce = async () => {
      try {
        const data = await checkJobStatus(jobId)
        if (!mounted) return
        
        if (data.status !== statusRef.current) {
          
          setStatus(data.status)
        }
        if (data.result != null && data.result !== resultRef.current) {
          
          setResult(data.result)
        }
        if (data.result && typeof data.result.progress === 'number' && data.result.progress !== progressRef.current) {
          
          setProgressPct(data.result.progress)
        }

        if (data.status === 'done') {
          // download results once
          if (!downloadedRef.done) {
            downloadedRef.done = true
            rememberVideoAnalysisJob(jobId)
            try {
              const dl = await downloadResults(jobId)
              if (!mounted) return
              // only update downloadData if different reference
              if (dl !== downloadData) {
                
                setDownloadData(dl)
              }
            } catch (err) {
              // ignore
            }
          }
          stopPolling()
        }
        if (data.status === 'failed') {
          stopPolling()
        }
      } catch (err) {
        if (!mounted) return
        
        setStatus('failed')
        try {
          const resp = (err as any)?.response?.data?.data
          if (resp && resp.result) setResult(resp.result)
        } catch {}
        stopPolling()
      }
    }

    // initial immediate poll, then interval
    
    void pollOnce()
    intervalId = window.setInterval(() => void pollOnce(), 1500)

    return () => {
      mounted = false
      stopPolling()
    }
  }, [jobId])

  useEffect(() => {
    const mediaUrl = downloadData?.annotated_video ?? null

    if (!mediaUrl) {
      if (videoObjectUrlRef.current) {
        URL.revokeObjectURL(videoObjectUrlRef.current)
        videoObjectUrlRef.current = null
      }
      lastResolvedVideoUrlRef.current = null
      setVideoUrl(null)
      setMediaLoaded(false)
      return
    }

    if (lastResolvedVideoUrlRef.current === mediaUrl && videoObjectUrlRef.current) {
      setVideoUrl(videoObjectUrlRef.current)
      return
    }

    let active = true

    async function resolveVideo() {
      // Prefer a short-lived signed streaming URL (supports Range) for native playback
      let resolvedUrl: string | null = null
      try {
        if (jobId) {
          resolvedUrl = await getAnnotatedStreamUrl(jobId)
        }
      } catch {}

      // If stream token wasn't available, fall back to blob-based authenticated fetch
      if (!resolvedUrl) {
        try {
          resolvedUrl = await createAuthenticatedMediaUrl(mediaUrl)
        } catch {}
      }

      if (!active) return

      const nextBlobUrl = resolvedUrl && resolvedUrl.startsWith('blob:') ? resolvedUrl : (resolvedUrl ?? null)

      if (videoObjectUrlRef.current && videoObjectUrlRef.current !== nextBlobUrl) {
        URL.revokeObjectURL(videoObjectUrlRef.current)
      }

      if (nextBlobUrl) {
        videoObjectUrlRef.current = nextBlobUrl
        lastResolvedVideoUrlRef.current = mediaUrl
        if (videoUrlRef.current !== nextBlobUrl) setVideoUrl(nextBlobUrl)
      } else {
        videoObjectUrlRef.current = null
        lastResolvedVideoUrlRef.current = null
        if (videoUrlRef.current !== null) setVideoUrl(null)
      }

      if (mediaLoaded) setMediaLoaded(false)
    }

    void resolveVideo()

    return () => {
      active = false
    }
  }, [downloadData?.annotated_video])

  // Resolve authenticated blob URLs for thumbnails/snapshots.
  // Depend on `downloadData` instead of the derived `vehicles`/`snapshots`
  // to avoid running this effect every render (those arrays are recreated).
  useEffect(() => {
    
    const urls = Array.from(new Set([
      ...vehicles.map((vehicle: any) => vehicle.thumbnail).filter(Boolean),
      ...snapshots.map((snapshot: any) => snapshot.image_url || snapshot.image).filter(Boolean),
    ]))

    if (!urls.length) {
      setImageUrls({})
      return
    }

    let active = true
    const nextMap: Record<string, string> = {}
    const pending = urls.map(async (url) => {
      const cached = imageObjectUrlsRef.current[url]
      if (cached) {
        nextMap[url] = cached
        return
      }

      const resolved = await createAuthenticatedMediaUrl(url)
      if (!active) return
      if (resolved && resolved.startsWith('blob:')) {
        imageObjectUrlsRef.current[url] = resolved
        nextMap[url] = resolved
      }
    })

    void Promise.all(pending).then(() => {
      if (active) setImageUrls(nextMap)
    })

    return () => {
      active = false
    }
  }, [downloadData])

  useEffect(() => {
    return () => {
      if (videoObjectUrlRef.current) {
        URL.revokeObjectURL(videoObjectUrlRef.current)
        videoObjectUrlRef.current = null
      }
      Object.values(imageObjectUrlsRef.current).forEach((blobUrl) => URL.revokeObjectURL(blobUrl))
      imageObjectUrlsRef.current = {}
    }
  }, [])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    video.muted = true
    video.volume = volume
    video.defaultPlaybackRate = playbackRate
    if (videoUrl) {
      const tryPlay = async () => {
        try {
          await video.play()
          setIsPlaying(true)
        } catch {
          setIsPlaying(false)
        }
      }
      tryPlay()
    }
  }, [videoUrl, playbackRate, volume])

  async function handleUpload() {
    if (!file) return
    const currentlyAnalyzing = uploading || (jobId && status && status !== 'done' && status !== 'failed')
    if (currentlyAnalyzing) return
    setUploading(true)
    setSelectedVehicleId(null)
    setActiveTab('review')
    try {
      const id = await uploadVideo(file)
      setJobId(id)
      setStatus('pending')
      setProgressPct(1)
      rememberVideoAnalysisJob(id)
    } catch (err) {
      setStatus('failed')
    } finally { setUploading(false) }
  }

  async function handleDownloadAnnotated(e: any) {
    e.preventDefault()
    if (!jobId) return
    try {
      const streamUrl = await getAnnotatedStreamUrl(jobId)
      if (!streamUrl) return
      const resp = await fetch(streamUrl)
      if (!resp.ok) return
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `annotated_${jobId}.mp4`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Download annotated failed', err)
    }
  }

  async function handleDiscardAnalysis() {
    if (!jobId) return
    const ok = window.confirm('Discard this analysis and delete temporary files?')
    if (!ok) return
    try {
      await discardAnalysis(jobId)
    } catch (err) {
      console.error('Discard failed', err)
    }

    // clear frontend state
    setDownloadData(null)
    setResult(null)
    setJobId(null)
    setStatus(null)
    setProgressPct(0)
    setFile(null)
    setSelectedVehicleId(null)
    setVideoUrl(null)
    if (videoObjectUrlRef.current) {
      try { URL.revokeObjectURL(videoObjectUrlRef.current) } catch {}
      videoObjectUrlRef.current = null
    }
    Object.values(imageObjectUrlsRef.current).forEach((u) => { try { URL.revokeObjectURL(u) } catch {} })
    imageObjectUrlsRef.current = {}
  }

  const filteredVehicles = vehicles.filter((vehicle:any) => {
    if (vehicleFilter === 'all') return true
    if (vehicleFilter === 'violations') return vehicle.violation
    return vehicle.vehicle_type === vehicleFilter
  }).filter((vehicle:any) => {
    if (!searchQuery) return true
    const needle = searchQuery.toLowerCase()
    return String(vehicle.track_id).includes(needle) || String(vehicle.plate ?? '').toLowerCase().includes(needle)
  })

  const selectedVehicle = filteredVehicles.find((v:any) => String(v.track_id) === String(selectedVehicleId)) ?? vehicles.find((v:any) => String(v.track_id) === String(selectedVehicleId))

  useEffect(() => {
    if (!selectedVehicle || !videoRef.current) return
    const time = selectedVehicle.first_seen ?? selectedVehicle.last_seen ?? 0
    videoRef.current.currentTime = time
  }, [selectedVehicle])

  useEffect(() => {
    if (!downloadData || !vehicles.length) {
      if (selectedVehicleId !== null) {
        lastAutoSelectedVehicle.current = null
      }
      return
    }

    const nextVehicleId = String(vehicles[0].track_id)
    if (selectedVehicleId === null && lastAutoSelectedVehicle.current !== nextVehicleId) {
      lastAutoSelectedVehicle.current = nextVehicleId
      
      setSelectedVehicleId(nextVehicleId)
      return
    }

    if (selectedVehicleId !== null) {
      lastAutoSelectedVehicle.current = String(selectedVehicleId)
    }
  }, [downloadData, selectedVehicleId, vehicles])

  // NOTE: automatic restoration of previously completed jobs has been disabled
  // to enforce an explicit upload → analyze → results workflow per-user session.

  // Render overlay synchronized to video currentTime by interpolating between frames
  function renderOverlay() {
    const v = videoRef.current
    const c = canvasRef.current
    const full = downloadData?.full_results ?? downloadData?.result
    if (!v || !c || !full || !full.frames) return

    // size the canvas to video display size
    const rect = v.getBoundingClientRect()
    c.width = rect.width
    c.height = rect.height
    c.style.width = `${rect.width}px`
    c.style.height = `${rect.height}px`

    const ctx = c.getContext('2d')
    if (!ctx) return
    ctx.clearRect(0,0,c.width,c.height)

    const t = v.currentTime
    const frames = full.frames
    // find surrounding frames
    let i = 0
    while (i < frames.length - 1 && frames[i+1].time < t) i++
    const f0 = frames[i]
    const f1 = frames[Math.min(i+1, frames.length-1)]
    const dt = Math.max(0.0001, f1.time - f0.time)
    const alpha = f0 === f1 ? 0 : Math.min(1, (t - f0.time) / dt)

    // build map of detections by track_id for interpolation
    const map0: Record<string, any> = {}
    for (const d of (f0.detections || [])) map0[String(d.track_id)] = d
    const map1: Record<string, any> = {}
    for (const d of (f1.detections || [])) map1[String(d.track_id)] = d

    // draw each detection present in either frame
    const trackIds = new Set<string>([...Object.keys(map0), ...Object.keys(map1)])
    for (const tid of trackIds) {
      const a = map0[tid]
      const b = map1[tid]
      let bbox: number[] | null = null
      let cls = ''
      let conf: number | null = null
      let speed: number | null = null
      let plate: string | null = null
      if (a && b) {
        // interpolate bbox arrays [x1,y1,x2,y2]
        bbox = [
          a.bbox[0] + (b.bbox[0]-a.bbox[0])*alpha,
          a.bbox[1] + (b.bbox[1]-a.bbox[1])*alpha,
          a.bbox[2] + (b.bbox[2]-a.bbox[2])*alpha,
          a.bbox[3] + (b.bbox[3]-a.bbox[3])*alpha,
        ]
        cls = a.class || b.class || ''
        conf = (a.confidence ?? b.confidence) ?? null
        speed = (a.speed_kmh ?? b.speed_kmh) ?? null
        plate = a.plate ?? b.plate ?? null
      } else if (a) {
        bbox = a.bbox
        cls = a.class
        conf = a.confidence ?? null
        speed = a.speed_kmh ?? null
        plate = a.plate ?? null
      } else if (b) {
        bbox = b.bbox
        cls = b.class
        conf = b.confidence ?? null
        speed = b.speed_kmh ?? null
        plate = b.plate ?? null
      }
      if (!bbox) continue

      // normalized bbox to pixel coordinates
      const x1 = bbox[0] * c.width
      const y1 = bbox[1] * c.height
      const x2 = bbox[2] * c.width
      const y2 = bbox[3] * c.height
      const w = Math.max(2, x2 - x1)
      const h = Math.max(2, y2 - y1)

      // draw box
      ctx.strokeStyle = 'red'
      ctx.lineWidth = 2
      ctx.strokeRect(x1, y1, w, h)

      // label
      const labels = [cls]
      if (conf) labels.push(`${(conf*100).toFixed(0)}%`)
      if (speed) labels.push(`${Math.round(speed)} km/h`)
      if (plate) labels.push(String(plate))
      const text = labels.filter(Boolean).join(' | ')
      ctx.fillStyle = 'red'
      ctx.font = '12px Arial'
      const pad = 4
      const textW = ctx.measureText(text).width + pad*2
      const textH = 16
      ctx.fillRect(x1, Math.max(0, y1 - textH - 4), textW, textH)
      ctx.fillStyle = 'white'
      ctx.fillText(text, x1 + pad, Math.max(0, y1 - 6))
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Video Analysis</h1>
            <p className="mt-1 text-sm text-slate-500">Upload a traffic video to run the full AI analysis pipeline (YOLO → Tracking → OCR → Speed → Violations).</p>
          </div>
          <div className="space-y-2 rounded-3xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
            <div>Job status</div>
            <div className="text-slate-900 font-semibold">{status ?? 'idle'}</div>
            <div className="text-xs">Job: {jobId ?? 'n/a'}</div>
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="grid gap-4 lg:grid-cols-[1.3fr_0.7fr] items-end">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Upload a video for temporary AI analysis</label>
            <input type="file" accept="video/*" onChange={e => setFile(e.target.files ? e.target.files[0] : null)} className="block w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700" />
          </div>
          <div className="flex flex-wrap gap-2 justify-end">
            <button onClick={handleUpload} disabled={!file || isAnalyzing}
              className="rounded-2xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
              {uploading ? 'Uploading…' : isAnalyzing ? 'Analyzing Video...' : 'Start Analysis'}
            </button>
            <button onClick={() => { if (videoRef.current) videoRef.current.requestFullscreen?.() }}
              className="rounded-2xl border border-slate-200 bg-slate-50 px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-100">Fullscreen</button>
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Processing progress</div>
            <div className="mt-2 text-lg font-semibold text-slate-900">{progressPct}%</div>
          </div>
          <div className="flex-1">
            <ProgressBar pct={progressPct} />
          </div>
        </div>
      </div>

      {status === 'failed' && result?.error && (
        <div className="rounded-3xl border border-red-200 bg-red-50 p-4 shadow-sm">
          <div className="text-sm font-semibold text-red-700">Processing failed</div>
          <div className="mt-2 text-xs text-red-600">{result.error}</div>
          {result.traceback && (
            <pre className="mt-3 max-h-48 overflow-auto text-xs text-slate-700 bg-white p-3 rounded">{result.traceback}</pre>
          )}
        </div>
      )}

      {downloadData && (
        <div className="grid gap-4 xl:grid-cols-[1.6fr_0.95fr]">
          <div className="space-y-4">
            <div className="rounded-3xl border border-slate-200 bg-slate-900 p-4 shadow-sm">
              <div className="relative overflow-hidden rounded-[28px] border border-slate-700 bg-black shadow-inner">
                {downloadData.annotated_video ? (
                  <>
                    <video
                      ref={videoRef}
                      controls
                      autoPlay
                      muted
                      src={videoUrl ?? undefined}
                      className="relative z-0 w-full h-[560px] bg-black object-cover"
                      onLoadedMetadata={() => {
                        const v = videoRef.current
                        if (v) {
                          setDuration(v.duration)
                          setMediaLoaded(true)
                        }
                      }}
                      onCanPlay={() => setMediaLoaded(true)}
                      onTimeUpdate={() => {
                        const v = videoRef.current
                        if (v) {
                          const newTime = v.currentTime
                          setCurrentTime(newTime)
                          renderOverlay()
                        }
                      }}
                    >
                      Your browser does not support the video tag.
                    </video>
                    <canvas
                      ref={canvasRef}
                      style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 10 }}
                      className="pointer-events-none"
                    />
                  </>
                ) : (
                  <div className="relative rounded-[28px] bg-slate-950 p-4">
                    <canvas ref={canvasRef} className="w-full h-80 rounded-[28px] bg-slate-900" />
                    <div className="pointer-events-none absolute inset-x-0 bottom-4 mx-auto w-full text-center text-xs text-slate-300">Video preview not available yet; using first available annotated frame for inspection.</div>
                  </div>
                )}
              </div>

              <div className="grid gap-4 lg:grid-cols-[1fr_auto] mt-4">
                <div className="rounded-3xl border border-slate-700 bg-slate-950/80 p-4 text-slate-200">
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div>
                      <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Annotated MP4</div>
                      <div className="mt-2 text-lg font-semibold text-white">Review and evidence playback</div>
                    </div>
                    <div className="text-right text-sm text-slate-400">
                      {duration && mediaLoaded ? `${currentTime.toFixed(1)}s / ${duration.toFixed(1)}s` : 'Loading video...'}
                    </div>
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div className="rounded-2xl bg-slate-900 p-3 text-sm">
                      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Speed calibration</div>
                      <div className="mt-2 text-white">
                        {isCalibrated
                          ? 'Calibrated to camera geometry'
                          : 'Speed unavailable (Camera not calibrated)'}
                      </div>
                    </div>
                    <div className="rounded-2xl bg-slate-900 p-3 text-sm">
                      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Playback mode</div>
                      <div className="mt-2 text-white">{isPlaying ? 'Playing' : 'Ready for review'}</div>
                    </div>
                  </div>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Developer Tools</div>
                      <div className="mt-2 text-lg font-semibold text-slate-900">Advanced playback</div>
                    </div>
                    <button onClick={() => setShowDevTools(prev => !prev)} className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100">
                      {showDevTools ? 'Hide' : 'Show'}
                    </button>
                  </div>
                  {showDevTools ? (
                    <div className="mt-4 grid gap-3">
                      <div className="grid gap-3 sm:grid-cols-2">
                        <button onClick={() => { if (videoRef.current) videoRef.current.currentTime = Math.max(0, videoRef.current.currentTime - 1) }} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 hover:bg-slate-100">Frame ◀</button>
                        <button onClick={() => { if (videoRef.current) videoRef.current.currentTime = Math.min(videoRef.current.duration, videoRef.current.currentTime + 1) }} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 hover:bg-slate-100">Frame ▶</button>
                        <button onClick={() => { if (videoRef.current) videoRef.current.currentTime = Math.max(0, videoRef.current.currentTime - 0.5) }} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 hover:bg-slate-100">Prev detection</button>
                        <button onClick={() => { if (videoRef.current) videoRef.current.currentTime = Math.min(videoRef.current.duration, videoRef.current.currentTime + 0.5) }} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 hover:bg-slate-100">Next detection</button>
                      </div>
                      {!downloadData.annotated_video && (
                        <div className="grid gap-3 sm:grid-cols-3">
                          <button onClick={() => setFallbackFrameIndex(Math.max(0, fallbackFrameIndex - 1))} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 hover:bg-slate-100">Prev frame</button>
                          <button onClick={() => setFallbackFrameIndex(Math.min((results?.frames?.length ?? 1) - 1, fallbackFrameIndex + 1))} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 hover:bg-slate-100">Next frame</button>
                          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">Frame {fallbackFrameIndex + 1} / {results?.frames?.length ?? 0}</div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="mt-4 rounded-2xl bg-slate-50 p-3 text-sm text-slate-500">Hidden except for diagnostics or detailed review.</div>
                  )}
                </div>
              </div>

              <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Timeline</div>
                    <div className="mt-2 text-lg font-semibold text-slate-900">Interactive event timeline</div>
                  </div>
                  <div className="text-xs text-slate-500">Jump to first appearance, plate, speed, or violation events.</div>
                </div>
                <Timeline
                  duration={duration}
                  events={timelineEvents}
                  onSeek={(t:number) => { if (videoRef.current) videoRef.current.currentTime = t }}
                />
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Vehicle review</div>
                    <div className="mt-1 text-lg font-semibold text-slate-900">{filteredVehicles.length} vehicles found</div>
                  </div>
                  <button onClick={() => setSelectedVehicleId(filteredVehicles[0]?.track_id ?? null)} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700 hover:bg-slate-200">Select first</button>
                </div>
                <div className="mt-4 flex flex-col gap-3">
                  <div className="grid grid-cols-2 gap-2">
                    <button onClick={() => { if (videoRef.current) videoRef.current.currentTime = Math.max(0, (videoRef.current.currentTime - 1)) }} className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100">← Frame step</button>
                    <button onClick={() => { if (videoRef.current) videoRef.current.currentTime = Math.min(videoRef.current.duration, (videoRef.current.currentTime + 1)) }} className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100">Frame step →</button>
                    <button onClick={() => { const next = violations.find((v:any) => v.time > (videoRef.current?.currentTime ?? 0)); if (next && videoRef.current) videoRef.current.currentTime = next.time }} className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100">Next violation</button>
                    <button onClick={() => { const prev = [...violations].reverse().find(v => v.time < (videoRef.current?.currentTime ?? Infinity)); if (prev && videoRef.current) videoRef.current.currentTime = prev.time }} className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100">Prev violation</button>
                  </div>
                  <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Search</label>
                  <input type="text" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Track or plate" className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 focus:border-blue-500 focus:outline-none" />
                  <div className="flex flex-wrap gap-2">
                    <button onClick={() => setVehicleFilter('all')} className={`rounded-full px-3 py-1 text-xs ${vehicleFilter === 'all' ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-700'}`}>All</button>
                    <button onClick={() => setVehicleFilter('violations')} className={`rounded-full px-3 py-1 text-xs ${vehicleFilter === 'violations' ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-700'}`}>Violations</button>
                    {['car','truck','bus','motorcycle','person'].map(type => (
                      <button key={type} onClick={() => setVehicleFilter(type)} className={`rounded-full px-3 py-1 text-xs ${vehicleFilter === type ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-700'}`}>{type}</button>
                    ))}
                  </div>

                  <div className="rounded-3xl border border-slate-200 bg-slate-50 p-3">
                    <VirtualList items={filteredVehicles} itemHeight={134} containerHeight={420} renderItem={(vehicle:any) => (
                      <VehicleCard vehicle={vehicle} isSelected={String(selectedVehicleId) === String(vehicle.track_id)} onSelect={setSelectedVehicleId} isCalibrated={isCalibrated} plateConfidenceThreshold={plateConfidenceThreshold} imageSrc={imageUrls[vehicle.thumbnail] ?? vehicle.thumbnail} />
                    )} />
                  </div>
                </div>
              </div>

              <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-sm font-semibold text-slate-900">Selected vehicle stats</div>
                {selectedVehicle ? (
                  <div className="mt-4 grid gap-3 text-sm text-slate-700">
                    <div className="grid grid-cols-2 gap-3 rounded-2xl bg-slate-50 p-3">
                      <div>
                        <div className="text-xs text-slate-500">Travel duration</div>
                        <div className="text-base font-semibold text-slate-900">{selectedVehicle.duration_seconds ? formatDuration(selectedVehicle.duration_seconds) : '-'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-slate-500">Frames tracked</div>
                        <div className="text-base font-semibold text-slate-900">{selectedVehicle.frames?.length ?? 0}</div>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3 rounded-2xl bg-slate-50 p-3">
                      <div>
                        <div className="text-xs text-slate-500">Average speed</div>
                        <div className="text-base font-semibold text-slate-900">{selectedVehicle.avg_speed ? `${selectedVehicle.avg_speed.toFixed(0)} km/h` : '-'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-slate-500">Maximum speed</div>
                        <div className="text-base font-semibold text-slate-900">{selectedVehicle.max_speed ? `${selectedVehicle.max_speed.toFixed(0)} km/h` : '-'}</div>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3 rounded-2xl bg-slate-50 p-3">
                      <div>
                        <div className="text-xs text-slate-500">Plate confidence</div>
                        <div className="text-base font-semibold text-slate-900">{selectedVehicle.plate_confidence ? `${Math.round(selectedVehicle.plate_confidence * 100)}%` : '-'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-slate-500">Violation confidence</div>
                        <div className="text-base font-semibold text-slate-900">{selectedVehicle.violation ? `${Math.round((selectedVehicle.confidence_history?.slice(-1)[0] ?? 0) * 100)}%` : 'N/A'}</div>
                      </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">
                      <div className="font-semibold text-slate-900">Confidence trend</div>
                      <div className="mt-2 h-32">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={(selectedVehicle.confidence_history || []).map((confidence:number, index:number) => ({ index, confidence }))}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                            <XAxis dataKey="index" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                            <YAxis domain={[0, 1]} tickFormatter={(value) => `${Math.round(value*100)}%`} tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                            <Tooltip formatter={(value:number) => `${Math.round(value*100)}%`} />
                            <Line type="monotone" dataKey="confidence" stroke="#2563eb" strokeWidth={2} dot={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="mt-4 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">Select a vehicle card to inspect its detailed statistics.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {downloadData && (
        <div className="space-y-4">
          <DashboardCards
            uniqueVehicles={uniqueVehicles}
            totalDetections={totalDetections}
            vehicleTypeCounts={vehicleTypeCounts}
            averageSpeed={averageSpeed}
            highestSpeed={highestSpeed}
            recognizedPlates={recognizedPlates}
            violationCount={violationCount}
          />
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Download and report</h2>
                <p className="text-sm text-slate-500">Export artifact packages for investigation and evidence.</p>
              </div>
              <div className="flex flex-wrap gap-3">
                {downloadData.annotated_video && (
                  <>
                    <button onClick={handleDownloadAnnotated} className="rounded-2xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white hover:bg-slate-800">Download Annotated Video</button>
                    <button onClick={() => window.open(downloadData.annotated_video, '_blank')} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50">Open raw URL</button>
                    <button onClick={handleDiscardAnalysis} className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700 hover:bg-red-100">Discard Analysis</button>
                  </>
                )}
                {downloadData.result && (
                  <button onClick={(e)=>{e.preventDefault(); const blob = new Blob([JSON.stringify(downloadData.full_results ?? downloadData.result, null, 2)], {type:'application/json'}); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'results.json'; a.click();}} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50">JSON export</button>
                )}
                {downloadData.result?.csv_url && (
                  <a href={downloadData.result.csv_url} target="_blank" rel="noreferrer" className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50">Download CSV</a>
                )}
                {downloadData.result?.pdf_url && (
                  <a href={downloadData.result.pdf_url} target="_blank" rel="noreferrer" className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50">Download PDF Report</a>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default UploadVideoPanel

// Keep helper components referenced so TypeScript's "noUnusedLocals" doesn't fail during build
const _keepHelpers = [ReviewTabs, SnapshotGallery, MetadataPanel, TrackingHistoryPanel]
void _keepHelpers
