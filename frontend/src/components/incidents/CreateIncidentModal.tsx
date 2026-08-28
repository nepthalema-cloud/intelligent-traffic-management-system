import { type FormEvent, useState, useEffect } from 'react'
import { Modal } from '@/components/ui/Modal'
import { FormField, inputCls } from '@/components/ui/FormField'
import { incidentService } from '@/services/traffic.service'
import { roadsService } from '@/services/roads.service'
import type { Intersection, RoadSegment } from '@/types/api'

interface Props {
  open: boolean
  onClose: () => void
  onCreated: () => void
}

const INCIDENT_TYPES = [
  { value: 'accident',     label: '💥 Accident' },
  { value: 'road_closure', label: '🚧 Road Closure' },
  { value: 'hazard',       label: '⚠️ Hazard' },
  { value: 'flooding',     label: '🌊 Flooding' },
  { value: 'fire',         label: '🔥 Fire' },
  { value: 'other',        label: '📌 Other' },
]

export function CreateIncidentModal({ open, onClose, onCreated }: Props) {
  const [title, setTitle]         = useState('')
  const [description, setDesc]    = useState('')
  const [incidentType, setType]   = useState('accident')
  const [occurredAt, setOccurred] = useState('')
  const [intersectionId, setInt]  = useState<string>('')
  const [intersections, setIntersections] = useState<Intersection[]>([])
  const [segments, setSegments]   = useState<RoadSegment[]>([])
  const [selectedSegs, setSegs]   = useState<number[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError]         = useState<string | null>(null)

  // Pre-fill occurred_at with current datetime-local string
  useEffect(() => {
    if (open) {
      const now = new Date()
      now.setMinutes(now.getMinutes() - now.getTimezoneOffset())
      setOccurred(now.toISOString().slice(0, 16))
      setError(null)
    }
  }, [open])

  // Load intersections + segments for dropdowns
  useEffect(() => {
    if (!open) return
    Promise.all([
      roadsService.listIntersections({ page_size: 100 }),
      roadsService.listSegments({ page_size: 100 }),
    ]).then(([i, s]) => {
      setIntersections(i.results)
      setSegments(s.results)
    }).catch(() => {/* silently ignore — dropdowns just stay empty */})
  }, [open])

  function toggleSeg(id: number) {
    setSegs(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await incidentService.create({
        title,
        description,
        incident_type: incidentType,
        occurred_at: new Date(occurredAt).toISOString(),
        intersection: intersectionId ? Number(intersectionId) : null,
        segment_ids: selectedSegs,
      })
      setTitle(''); setDesc(''); setType('accident'); setInt(''); setSegs([])
      onCreated()
      onClose()
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { message?: string } } }
      setError(apiErr?.response?.data?.message ?? 'Failed to create incident.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Report New Incident" maxWidth="lg">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="rounded-lg border border-red-800 bg-red-950 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        <FormField label="Title" htmlFor="inc-title" required>
          <input id="inc-title" className={inputCls} value={title}
            onChange={e => setTitle(e.target.value)} required maxLength={255}
            placeholder="e.g. Multi-vehicle accident on Uhuru Highway" />
        </FormField>

        <div className="grid grid-cols-2 gap-3">
          <FormField label="Type" htmlFor="inc-type" required>
            <select id="inc-type" className={inputCls} value={incidentType}
              onChange={e => setType(e.target.value)}>
              {INCIDENT_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </FormField>

          <FormField label="Occurred at" htmlFor="inc-occurred" required>
            <input id="inc-occurred" type="datetime-local" className={inputCls}
              value={occurredAt} onChange={e => setOccurred(e.target.value)} required />
          </FormField>
        </div>

        <FormField label="Description" htmlFor="inc-desc" required>
          <textarea id="inc-desc" className={inputCls} rows={3} value={description}
            onChange={e => setDesc(e.target.value)} required
            placeholder="Describe the incident…" />
        </FormField>

        <FormField label="Intersection (optional)" htmlFor="inc-int">
          <select id="inc-int" className={inputCls} value={intersectionId}
            onChange={e => setInt(e.target.value)}>
            <option value="">— None —</option>
            {intersections.map(i => (
              <option key={i.id} value={i.id}>{i.name}</option>
            ))}
          </select>
        </FormField>

        {segments.length > 0 && (
          <FormField label="Affected segments (optional)" htmlFor="inc-segs">
            <div className="max-h-28 overflow-y-auto space-y-1 rounded-lg border border-gray-700 bg-gray-800 p-2">
              {segments.map(s => (
                <label key={s.id} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer hover:text-white">
                  <input type="checkbox" checked={selectedSegs.includes(s.id)}
                    onChange={() => toggleSeg(s.id)}
                    className="rounded border-gray-600 bg-gray-700 text-cyan-500" />
                  {s.name} ({s.road_name})
                </label>
              ))}
            </div>
          </FormField>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose}
            className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-400 hover:bg-gray-800">
            Cancel
          </button>
          <button type="submit" disabled={submitting}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500 disabled:opacity-50">
            {submitting ? 'Reporting…' : 'Report Incident'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
