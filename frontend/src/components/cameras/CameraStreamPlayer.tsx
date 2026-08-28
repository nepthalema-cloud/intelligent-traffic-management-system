/**
 * CameraStreamPlayer — HLS video player for CCTV camera streams.
 *
 * Architecture:
 *   CCTV Camera (RTSP)
 *     → MediaMTX (server-side transcoding, credentials NOT in browser)
 *     → HLS .m3u8 (safe to serve to browser)
 *     → <video> via hls.js
 *
 * The raw RTSP URL and any camera credentials are NEVER sent to the browser.
 * This component receives only the safe HLS URL from the backend API.
 *
 * Displays clearly:
 *   - "TEST SOURCE" label if is_test_source=true
 *   - "LIVE CAMERA" label if real IP camera
 *   - Offline state if stream unavailable
 *   - Connection state and last frame time
 */

import { useEffect, useRef, useState } from 'react'
import type { CameraStream } from '@/types/api'

interface CameraStreamPlayerProps {
  stream: CameraStream
  className?: string
}

type PlayerState = 'loading' | 'playing' | 'error' | 'unavailable'

export function CameraStreamPlayer({ stream, className = '' }: CameraStreamPlayerProps) {
  const videoRef    = useRef<HTMLVideoElement>(null)
  const hlsRef      = useRef<unknown>(null)
  const [state, setState] = useState<PlayerState>('loading')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!stream.available || !stream.hls_url) {
      setState('unavailable')
      return
    }

    const video = videoRef.current
    if (!video) return

    let hls: unknown = null

    async function initPlayer() {
      setState('loading')
      setError(null)

      try {
        // Dynamic import so hls.js doesn't bloat non-camera pages
        const HlsModule = await import('hls.js')
        const Hls = HlsModule.default

        if (Hls.isSupported()) {
          hls = new Hls({
            lowLatencyMode:      true,
            backBufferLength:    10,
            maxBufferLength:     20,
            enableWorker:        true,
          })
          hlsRef.current = hls

          ;(hls as { on: Function; attachMedia: Function; loadSource: Function }).on(Hls.Events.MEDIA_ATTACHED, () => {
            ;(hls as { loadSource: Function }).loadSource(stream.hls_url!)
          })
          ;(hls as { on: Function; attachMedia: Function }).on(Hls.Events.MANIFEST_PARSED, () => {
            if (video) {
              video.play().catch(() => { /* autoplay may be blocked */ })
            }
            setState('playing')
          })
          ;(hls as { on: Function }).on(Hls.Events.ERROR, (_: unknown, data: { fatal: boolean; type: string }) => {
            if (data.fatal) {
              setState('error')
              setError(`Stream error: ${data.type}`)
            }
          })

          if (video) {
            ;(hls as { attachMedia: Function }).attachMedia(video)
          }

        } else if (video && video.canPlayType('application/vnd.apple.mpegurl')) {
          // Native HLS support (Safari)
          video.src = stream.hls_url!
          video.play().catch(() => {})
          setState('playing')
        } else {
          setState('error')
          setError('HLS not supported in this browser.')
        }
      } catch (err) {
        setState('error')
        setError('Failed to load HLS player.')
      }
    }

    void initPlayer()

    return () => {
      if (hls) (hls as { destroy: Function }).destroy()
    }
  }, [stream.hls_url, stream.available])

  const sourceBadge = stream.is_test_source
    ? { label: '🎬 TEST SOURCE', cls: 'bg-amber-500 text-white' }
    : { label: '📹 LIVE CAMERA', cls: 'bg-emerald-600 text-white' }

  return (
    <div className={`relative rounded-xl overflow-hidden bg-slate-900 ${className}`}>
      {/* Video element */}
      {stream.available && (
        <video
          ref={videoRef}
          className="w-full h-full object-cover"
          muted
          playsInline
          controls={false}
        />
      )}

      {/* Unavailable overlay */}
      {(state === 'unavailable' || !stream.available) && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900 text-slate-400">
          <svg className="h-10 w-10 mb-3 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M15 10l4.553-2.069A1 1 0 0121 8.871v6.258a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            <line x1="4" y1="4" x2="20" y2="20" stroke="currentColor" strokeWidth={1.5}/>
          </svg>
          <p className="text-sm font-medium">Stream Unavailable</p>
          <p className="text-xs text-slate-500 mt-1 text-center px-4">
            {stream.reason ?? 'No active RTSP source is pushing to this stream path.'}
          </p>
          {stream.source_label?.includes('WEBCAM') && (
            <p className="text-[10px] text-amber-400 mt-2 text-center px-4">
              For browser webcam testing use "Start My Webcam" below — it does not require an RTSP stream.
            </p>
          )}
        </div>
      )}

      {/* Loading overlay */}
      {state === 'loading' && stream.available && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-900/80">
          <div className="flex items-center gap-2 text-sm text-slate-300">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-500 border-t-blue-400" />
            Connecting to stream…
          </div>
        </div>
      )}

      {/* Error overlay */}
      {state === 'error' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-red-950/80 text-red-300">
          <p className="text-sm font-medium">Stream Error</p>
          <p className="text-xs mt-1">{error}</p>
        </div>
      )}

      {/* HUD badges (only shown when playing) */}
      {state === 'playing' && (
        <>
          <div className="absolute top-2 left-2">
            <span className={`rounded-md px-2 py-0.5 text-[10px] font-bold ${sourceBadge.cls}`}>
              {sourceBadge.label}
            </span>
          </div>
          <div className="absolute top-2 right-2 flex items-center gap-1 rounded-md bg-black/50 px-2 py-0.5">
            <span className="h-1.5 w-1.5 rounded-full bg-red-500 animate-blink" />
            <span className="text-[10px] font-bold text-white">REC</span>
          </div>
          <div className="absolute bottom-2 left-2">
            <span className="rounded-md bg-black/50 px-2 py-0.5 text-[10px] text-slate-300">
              {stream.camera_name}
            </span>
          </div>
        </>
      )}
    </div>
  )
}
