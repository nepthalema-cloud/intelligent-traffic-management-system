import { type FormEvent, useState, useEffect } from 'react'
import { Modal } from '@/components/ui/Modal'
import { FormField, inputCls } from '@/components/ui/FormField'
import { eventService } from '@/services/traffic.service'
import { roadsService } from '@/services/roads.service'
import type { Intersection, RoadSegment } from '@/types/api'

interface Props {
  open: boolean
  onClose: () => void
  onCreated: () => void
}

const EVENT_TYPES = [
  { value: 'congestion',   label: '🔴 Congestion' },
  { value: 'incident',     label: '🚨 Incident' },
  { value: 'roadwork',     label: '🚧 Roadwork' },
  { value: 'weather',      label: '🌧️ Weather Hazard' },
  { value: 'signal_fault', label: '🚦 Signal Fault' },
  { value: 'other',        label: '📌 Other' },
]

export function CreateEventModal({ open, onClose, onCreated }: Props) {
  const [eventType, setType]      = useState('congestion')
  const [description, setDesc]    = useState('')
  const [occurredAt, setOccurred] = useState('')
  const [intersectionId, setInt]  = useState<string>('')
  const [segmentId, setSegment]   = useState<string>('')
  const [intersections, setIntersections] = useState<Intersection[]>([])
  const [segments, setSegments]   = useState<RoadSegment[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError]         = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      const now = new Date()
      now.setMinutes(now.getMinutes() - now.getTimezoneOffset())
      setOccurred(now.toISOString().slice(0, 16))
      setError(null)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    Promise.all([
      roadsService.listIntersections({ page_size: 100 }),
      roadsService.listSegments({ page_size: 100 }),
    ]).then(([i, s]) => {
      setIntersections(i.results)
      setSegments(s.results)
    }).catch(() => {})
  }, [open])

  // Can't have both intersection and segment
  function handleIntChange(val: string) { setInt(val); if (val) setSegment('') }
  function handleSegChange(val: string) { setSegment(val); if (val) setInt('') }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await eventService.create({
        event_type:   eventType,
        description,
        occurred_at:  new Date(occurredAt).toISOString(),
        intersection: intersectionId ? Number(intersectionId) : null,
        segment:      segmentId ? Number(segmentId) : null,
      })
      setDesc(''); setType('congestion'); setInt(''); setSegment('')
      onCreated()
      onClose()
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { message?: string } } }
      setError(apiErr?.response?.data?.message ?? 'Failed to create event.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Log Traffic Event" maxWidth="md">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="rounded-lg border border-red-800 bg-red-950 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <FormField label="Event type" htmlFor="evt-type" required>
            <select id="evt-type" className={inputCls} value={eventType}
              onChange={e => setType(e.target.value)}>
              {EVENT_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </FormField>

          <FormField label="Occurred at" htmlFor="evt-occurred" required>
            <input id="evt-occurred" type="datetime-local" className={inputCls}
              value={occurredAt} onChange={e => setOccurred(e.target.value)} required />
          </FormField>
        </div>

        <FormField label="Description" htmlFor="evt-desc" required>
          <textarea id="evt-desc" className={inputCls} rows={3} value={description}
            onChange={e => setDesc(e.target.value)} required
            placeholder="Describe the event…" />
        </FormField>

        <FormField label="Intersection (optional)" htmlFor="evt-int">
          <select id="evt-int" className={inputCls} value={intersectionId}
            onChange={e => handleIntChange(e.target.value)}>
            <option value="">— None —</option>
            {intersections.map(i => (
              <option key={i.id} value={i.id}>{i.name}</option>
            ))}
          </select>
        </FormField>

        <FormField label="Road segment (optional)" htmlFor="evt-seg">
          <select id="evt-seg" className={inputCls} value={segmentId}
            onChange={e => handleSegChange(e.target.value)}>
            <option value="">— None —</option>
            {segments.map(s => (
              <option key={s.id} value={s.id}>{s.name} ({s.road_name})</option>
            ))}
          </select>
        </FormField>

        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose}
            className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-400 hover:bg-gray-800">
            Cancel
          </button>
          <button type="submit" disabled={submitting}
            className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-500 disabled:opacity-50">
            {submitting ? 'Logging…' : 'Log Event'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
