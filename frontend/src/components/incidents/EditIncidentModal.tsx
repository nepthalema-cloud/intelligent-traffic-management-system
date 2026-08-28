import { type FormEvent, useState, useEffect } from 'react'
import { Modal } from '@/components/ui/Modal'
import { FormField, inputCls } from '@/components/ui/FormField'
import { incidentService } from '@/services/traffic.service'
import type { TrafficIncident } from '@/types/api'

interface Props {
  incident: TrafficIncident
  open: boolean
  onClose: () => void
  onSaved: (updated: TrafficIncident) => void
}

const INCIDENT_TYPES = [
  { value: 'accident',     label: '💥 Accident' },
  { value: 'road_closure', label: '🚧 Road Closure' },
  { value: 'hazard',       label: '⚠️ Hazard' },
  { value: 'flooding',     label: '🌊 Flooding' },
  { value: 'fire',         label: '🔥 Fire' },
  { value: 'other',        label: '📌 Other' },
]

export function EditIncidentModal({ incident, open, onClose, onSaved }: Props) {
  const [title,       setTitle]   = useState(incident.title)
  const [description, setDesc]    = useState(incident.description)
  const [incidentType, setType]   = useState(incident.incident_type)
  const [submitting,  setSub]     = useState(false)
  const [error,       setError]   = useState<string | null>(null)

  // Reset form whenever the incident changes or modal opens
  useEffect(() => {
    if (open) {
      setTitle(incident.title)
      setDesc(incident.description)
      setType(incident.incident_type)
      setError(null)
    }
  }, [open, incident])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSub(true); setError(null)
    try {
      const updated = await incidentService.update(incident.id, {
        title,
        description,
        incident_type: incidentType,
      })
      onSaved(updated)
      onClose()
    } catch (err: unknown) {
      const ae = err as { response?: { data?: { message?: string } } }
      setError(ae?.response?.data?.message ?? 'Failed to update incident.')
    } finally {
      setSub(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Edit Incident" maxWidth="md">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="rounded-lg border border-red-800 bg-red-950 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        <FormField label="Title" htmlFor="edit-inc-title" required>
          <input id="edit-inc-title" className={inputCls} value={title}
            onChange={e => setTitle(e.target.value)} required maxLength={255} />
        </FormField>

        <FormField label="Type" htmlFor="edit-inc-type" required>
          <select id="edit-inc-type" className={inputCls} value={incidentType}
            onChange={e => setType(e.target.value as TrafficIncident['incident_type'])}>
            {INCIDENT_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </FormField>

        <FormField label="Description" htmlFor="edit-inc-desc" required>
          <textarea id="edit-inc-desc" className={inputCls} rows={4} value={description}
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
