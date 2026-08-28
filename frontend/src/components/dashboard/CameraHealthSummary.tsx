import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { cameraService } from '@/services/cameras.service'
import type { Camera } from '@/types/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorMessage } from '@/components/ui/ErrorMessage'

const dotCls: Record<string, string> = {
  healthy: 'bg-emerald-400', degraded: 'bg-amber-400',
  offline: 'bg-red-500',    unknown:  'bg-slate-400',
}

export function CameraHealthSummary() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    cameraService.list({ page_size: 8 })
      .then(d => setCameras(d.results))
      .catch(() => setError('Could not load cameras.'))
      .finally(() => setLoading(false))
  }, [])

  const active   = cameras.filter(c => c.is_active).length
  const inactive = cameras.length - active

  return (
    <div className="card rounded-xl p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="section-title">Camera Fleet</h3>
        <Link to="/cameras" className="text-link">View all →</Link>
      </div>

      {loading && <LoadingSpinner size="sm" />}
      {!loading && error && <ErrorMessage message={error} />}
      {!loading && !error && cameras.length === 0 && (
        <EmptyState icon="📷" title="No cameras configured" />
      )}
      {!loading && !error && cameras.length > 0 && (
        <>
          <div className="mb-3 flex gap-4">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <span className="text-xs font-medium text-slate-700">{active} active</span>
            </div>
            {inactive > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-slate-300" />
                <span className="text-xs text-slate-500">{inactive} inactive</span>
              </div>
            )}
          </div>

          <ul className="space-y-1.5" role="list">
            {cameras.slice(0, 6).map(cam => (
              <li key={cam.id} className="flex items-center gap-2.5">
                <span className={`h-2 w-2 shrink-0 rounded-full ${cam.is_active ? dotCls['healthy'] : dotCls['offline']}`} />
                <span className="truncate text-xs text-slate-700 flex-1">{cam.name}</span>
                <span className="shrink-0 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500 capitalize">
                  {cam.camera_type}
                </span>
              </li>
            ))}
            {cameras.length > 6 && (
              <li className="text-xs text-slate-400 pt-1">+{cameras.length - 6} more</li>
            )}
          </ul>
        </>
      )}
    </div>
  )
}
