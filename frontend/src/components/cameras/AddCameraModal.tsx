/**
 * AddCameraModal — CCTV camera onboarding wizard.
 *
 * Security guarantees:
 * - Username/password are POSTed to backend only — never stored in frontend state
 *   beyond the lifetime of this form
 * - The RTSP URL with credentials is assembled server-side
 * - The HLS URL (credential-free) is what the frontend receives for playback
 * - Passwords are never logged or included in audit detail (enforced backend)
 *
 * Workflow:
 *   1. Fill camera details (name, type, IP, RTSP port/path, location)
 *   2. Optionally add credentials (stored securely backend-only)
 *   3. Submit → camera created + credentials stored
 *   4. Run connectivity test to verify pipeline state
 */

import { type FormEvent, useState, useEffect } from 'react'
import { Modal } from '@/components/ui/Modal'
import { FormField, inputCls } from '@/components/ui/FormField'
import { CameraConnectionBadge } from './CameraConnectionBadge'
import { cameraService } from '@/services/cameras.service'
import { roadsService } from '@/services/roads.service'
import type { Intersection, RoadSegment, CameraConnectionStatus } from '@/types/api'

interface Props {
  open: boolean
  onClose: () => void
  onCreated: () => void
}

const CAMERA_TYPES = [
  { value: 'fixed',   label: 'Fixed Camera' },
  { value: 'ptz',     label: 'PTZ (Pan-Tilt-Zoom)' },
  { value: 'thermal', label: 'Thermal Camera' },
  { value: 'other',   label: 'Other' },
]

export function AddCameraModal({ open, onClose, onCreated }: Props) {
  // Camera details
  const [name,         setName]         = useState('')
  const [cameraType,   setCameraType]   = useState('fixed')
  const [model,        setModel]        = useState('')
  const [ipAddress,    setIpAddress]    = useState('')
  const [rtspPort,     setRtspPort]     = useState('554')
  const [rtspPath,     setRtspPath]     = useState('/stream1')
  const [intersectionId, setIntId]      = useState<string>('')
  const [segmentId,    setSegmentId]    = useState<string>('')
  const [description,  setDescription]  = useState('')

  // Credentials (never logged, never shown after submission)
  const [rtspUser,  setRtspUser]  = useState('')
  const [rtspPass,  setRtspPass]  = useState('')
  const [showPass,  setShowPass]  = useState(false)
  const [hasCredentials, setHasCred] = useState(false)

  // Location options
  const [intersections, setIntersections] = useState<Intersection[]>([])
  const [segments,      setSegments]      = useState<RoadSegment[]>([])

  // Submission state
  const [submitting, setSubmitting] = useState(false)
  const [error,      setError]      = useState<string | null>(null)
  const [createdId,  setCreatedId]  = useState<number | null>(null)

  // Connectivity test state
  const [testing,    setTesting]    = useState(false)
  const [connStatus, setConnStatus] = useState<CameraConnectionStatus | null>(null)

  useEffect(() => {
    if (!open) return
    setError(null); setConnStatus(null); setCreatedId(null)
    Promise.all([
      roadsService.listIntersections({ page_size: 100 }),
      roadsService.listSegments({ page_size: 100 }),
    ]).then(([i, s]) => {
      setIntersections(i.results)
      setSegments(s.results)
    }).catch(() => {})
  }, [open])

  // Build stream_url and hls_path from IP + port + path
  function buildStreamUrl() {
    if (!ipAddress) return ''
    const port = rtspPort || '554'
    const path = rtspPath.startsWith('/') ? rtspPath : `/${rtspPath}`
    return `rtsp://${ipAddress}:${port}${path}`
  }

  function buildHlsPath() {
    if (!name) return ''
    const slug = name.toLowerCase().replace(/[^a-z0-9]/g, '-').replace(/-+/g, '-')
    return `/${slug}/index.m3u8`
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!name.trim()) { setError('Camera name is required.'); return }
    setSubmitting(true); setError(null)
    try {
      const streamUrl = buildStreamUrl()
      const hlsPath   = buildHlsPath()
      const cam = await cameraService.create({
        name:         name.trim(),
        camera_type:  cameraType,
        model:        model.trim(),
        description:  description.trim(),
        ip_address:   ipAddress.trim() || undefined,
        stream_url:   streamUrl,
        hls_path:     hlsPath,
        intersection: intersectionId ? Number(intersectionId) : null,
        segment:      segmentId      ? Number(segmentId)      : null,
      } as any)

      setCreatedId(cam.id)

      // Store credentials if provided — password is NOT returned
      if (rtspUser || rtspPass) {
        await cameraService.setCredentials(cam.id, rtspUser, rtspPass)
        setHasCred(true)
        // Clear credentials from component state immediately after storage
        setRtspUser(''); setRtspPass('')
      }

    } catch (err: unknown) {
      const ae = err as { response?: { data?: { message?: string; errors?: unknown } } }
      setError(ae?.response?.data?.message ?? 'Failed to create camera.')
    } finally {
      setSubmitting(false)
    }
  }

  async function runTest() {
    if (!createdId) return
    setTesting(true); setConnStatus(null)
    try {
      const result = await cameraService.test(createdId)
      setConnStatus(result)
    } catch {
      setConnStatus({
        state:       'rtsp_unreachable',
        state_label: 'Test Failed',
        colour:      'red',
        detail:      'Could not run connectivity test. Check network and try again.',
        checked_at:  new Date().toISOString(),
      })
    } finally {
      setTesting(false)
    }
  }

  function handleFinish() {
    onCreated()
    onClose()
    // Reset form
    setName(''); setCameraType('fixed'); setModel(''); setIpAddress('')
    setRtspPort('554'); setRtspPath('/stream1'); setDescription('')
    setRtspUser(''); setRtspPass(''); setCreatedId(null)
    setConnStatus(null); setHasCred(false)
  }

  const isCreated = createdId !== null
  const previewUrl = connStatus?.hls_url ?? null

  return (
    <Modal open={open} onClose={onClose} title="Add CCTV Camera" maxWidth="lg">
      {!isCreated ? (
        /* ── Step 1: Camera configuration form ── */
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Basic details */}
          <div className="grid grid-cols-2 gap-3">
            <FormField label="Camera Name" htmlFor="cam-name" required>
              <input id="cam-name" className={inputCls} value={name}
                onChange={e => setName(e.target.value)} required maxLength={255}
                placeholder="e.g. CAM-UHURU-001" />
            </FormField>
            <FormField label="Camera Type" htmlFor="cam-type" required>
              <select id="cam-type" className={inputCls} value={cameraType}
                onChange={e => setCameraType(e.target.value)}>
                {CAMERA_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </FormField>
          </div>

          <FormField label="Model / Hardware" htmlFor="cam-model">
            <input id="cam-model" className={inputCls} value={model}
              onChange={e => setModel(e.target.value)} placeholder="e.g. Hikvision DS-2CD2T47G2" />
          </FormField>

          {/* RTSP configuration */}
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-3">
            <p className="text-xs font-semibold text-slate-700 uppercase tracking-wider">RTSP Stream Configuration</p>
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <FormField label="Camera IP / Hostname" htmlFor="cam-ip" required>
                  <input id="cam-ip" className={inputCls} value={ipAddress}
                    onChange={e => setIpAddress(e.target.value)} required
                    placeholder="192.168.1.100" />
                </FormField>
              </div>
              <FormField label="RTSP Port" htmlFor="cam-port">
                <input id="cam-port" className={inputCls} value={rtspPort}
                  onChange={e => setRtspPort(e.target.value)} placeholder="554" />
              </FormField>
            </div>
            <FormField label="RTSP Path" htmlFor="cam-path">
              <input id="cam-path" className={inputCls} value={rtspPath}
                onChange={e => setRtspPath(e.target.value)} placeholder="/stream1" />
            </FormField>
            {ipAddress && (
              <div className="rounded-md bg-white border border-slate-200 px-3 py-2">
                <p className="text-xs text-slate-500 mb-0.5">Assembled RTSP URL (credentials not shown)</p>
                <code className="text-xs text-slate-700 break-all">{buildStreamUrl()}</code>
              </div>
            )}
          </div>

          {/* Credentials */}
          <div className="rounded-lg border border-amber-100 bg-amber-50 p-4 space-y-3">
            <p className="text-xs font-semibold text-amber-800 uppercase tracking-wider">
              RTSP Credentials (optional — stored securely, never exposed)
            </p>
            <div className="grid grid-cols-2 gap-3">
              <FormField label="Username" htmlFor="cam-user">
                <input id="cam-user" className={inputCls} value={rtspUser}
                  onChange={e => setRtspUser(e.target.value)} autoComplete="new-password"
                  placeholder="admin" />
              </FormField>
              <FormField label="Password" htmlFor="cam-pass">
                <div className="relative">
                  <input id="cam-pass" type={showPass ? 'text' : 'password'} className={inputCls}
                    value={rtspPass} onChange={e => setRtspPass(e.target.value)}
                    autoComplete="new-password" placeholder="••••••••" />
                  <button type="button" onClick={() => setShowPass(v => !v)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs">
                    {showPass ? 'Hide' : 'Show'}
                  </button>
                </div>
              </FormField>
            </div>
            <p className="text-[10px] text-amber-700">
              Credentials are stored server-side only. They are used by MediaMTX to pull the RTSP stream and are never returned via any API.
            </p>
          </div>

          {/* Location */}
          <div className="grid grid-cols-2 gap-3">
            <FormField label="Intersection" htmlFor="cam-int">
              <select id="cam-int" className={inputCls} value={intersectionId}
                onChange={e => { setIntId(e.target.value); if (e.target.value) setSegmentId('') }}>
                <option value="">— None —</option>
                {intersections.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
              </select>
            </FormField>
            <FormField label="Road Segment" htmlFor="cam-seg">
              <select id="cam-seg" className={inputCls} value={segmentId}
                onChange={e => { setSegmentId(e.target.value); if (e.target.value) setIntId('') }}>
                <option value="">— None —</option>
                {segments.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </FormField>
          </div>

          <FormField label="Description / Notes" htmlFor="cam-desc">
            <textarea id="cam-desc" className={inputCls} rows={2} value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Operational notes (optional)" />
          </FormField>

          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50">
              Cancel
            </button>
            <button type="submit" disabled={submitting}
              className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">
              {submitting ? 'Saving…' : 'Save Camera'}
            </button>
          </div>
        </form>

      ) : (
        /* ── Step 2: Connectivity test ── */
        <div className="space-y-5">
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3">
            <p className="text-sm font-semibold text-emerald-800">Camera saved successfully</p>
            <p className="text-xs text-emerald-700 mt-0.5">
              {hasCredentials ? 'Credentials stored securely.' : 'No credentials stored.'}
              {' '}Now test the connection to verify the full pipeline.
            </p>
          </div>

          {/* Connection test */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-slate-900">Pipeline Test</h3>
              <button type="button" onClick={runTest} disabled={testing}
                className="flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700 disabled:opacity-50">
                {testing
                  ? <><span className="h-3 w-3 animate-spin rounded-full border border-white/40 border-t-white" />Testing…</>
                  : '▶ Run Connection Test'}
              </button>
            </div>

            {connStatus && (
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-2">
                <CameraConnectionBadge status={connStatus} showDetail />
                <p className="text-[10px] text-slate-400">
                  Tested at {new Date(connStatus.checked_at).toLocaleTimeString()}
                </p>
              </div>
            )}

            {/* Pipeline states legend */}
            <div className="mt-3 grid grid-cols-2 gap-1 text-[10px] text-slate-500">
              {[
                ['○ Saved',            'Configuration saved'],
                ['✕ RTSP Unreachable', 'Network/firewall issue'],
                ['⚠ Auth Failed',      'Wrong credentials'],
                ['↗ Stream Connected', 'RTSP readable'],
                ['▶ HLS Available',    'Browser-ready stream'],
                ['⚡ AI Processing',    'YOLO detecting vehicles'],
                ['● Live',             'Full pipeline active'],
              ].map(([state, desc]) => (
                <div key={state} className="flex gap-1.5">
                  <span className="font-mono">{state.split(' ')[0]}</span>
                  <span>{state.split(' ').slice(1).join(' ')} — {desc}</span>
                </div>
              ))}
            </div>
          </div>

          {/* HLS preview if available */}
          {previewUrl && (
            <div>
              <p className="text-xs font-semibold text-slate-700 mb-2">
                Live Preview (HLS — no RTSP credentials in browser)
              </p>
              <div className="rounded-lg bg-slate-900 overflow-hidden aspect-video text-center flex items-center justify-center">
                <p className="text-xs text-slate-400">
                  HLS available: <code className="text-xs text-slate-300">{previewUrl}</code>
                  <br />Open the Cameras page to view the live stream.
                </p>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={handleFinish}
              className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700">
              Done
            </button>
          </div>
        </div>
      )}
    </Modal>
  )
}
