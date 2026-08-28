import { type FormEvent, useState, useEffect } from 'react'
import { Modal } from '@/components/ui/Modal'
import { FormField, inputCls } from '@/components/ui/FormField'
import { eventService } from '@/services/traffic.service'
import type { TrafficEvent } from '@/types/api'

interface Props {
  event: TrafficEvent
  open: boolean
  onClose: () => void
  onSaved: (updated: TrafficEvent) => void
}

const EVENT_TYPES = [
  { value: 'congestion',   label: '🔴 Congestion' },
  { value: 'incident',     label: '🚨 Incident' },
  { value: 'roadwork',     label: '🚧 Roadwork' },
  { value: 'weather',      label: '🌧️ Weather Hazard' },
  { value: 'signal_fault', label: '🚦 Signal Fault' },
  { value: 'other',        label: '📌 Other' },
]

export function EditEventModal({ event, open, onClose, onSaved }: Props) {
  const [eventType,   setType] = useState(event.event_type)
  const [description, setDesc] = useState(event.description)
  const [submitting,  setSub]  = useState(false)
  const [error,       setErr]  = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setType(event.event_type)
      setDesc(event.description)
      setErr(null)
    }
  }, [open, event])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSub(true); setErr(null)
    try {
      const updated = await eventService.update(event.id, {
        event_type: eventType,
        description,
      })
      onSaved(updated)
      onClose()
    } catch (err: unknown) {
      const ae = err as { response?: { data?: { message?: string } } }
      setErr(ae?.response?.data?.message ?? 'Failed to update event.')
    } finally {
      setSub(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Edit Event" maxWidth="md">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="rounded-lg border border-red-800 bg-red-950 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        <FormField label="Event type" htmlFor="edit-evt-type" required>
          <select id="edit-evt-type" className={inputCls} value={eventType}
            onChange={e => setType(e.target.value as TrafficEvent['event_type'])}>
            {EVENT_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </FormField>

        <FormField label="Description" htmlFor="edit-evt-desc" required>
          <textarea id="edit-evt-desc" className={inputCls} rows={4} value={description}
            onChange={e => setDesc(e.target.value)} required />
        </FormField>

        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose}
            className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-400 hover:bg-gray-800">
            Cancel
          </button>
          <button type="submit" disabled={submitting}
            className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-50">
            {submitting ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
