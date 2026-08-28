import { useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { incidentService } from '@/services/traffic.service'
import type { TrafficIncident, IncidentState } from '@/types/api'
import { StatusBadge } from '@/components/ui/StatusBadge'

// Valid forward transitions per state (mirrors backend VALID_TRANSITIONS)
const TRANSITIONS: Record<IncidentState, IncidentState[]> = {
  reported:      ['investigating', 'resolved'],
  investigating: ['managing', 'resolved'],
  managing:      ['resolved'],
  resolved:      ['closed'],
  closed:        [],
}

const STATE_LABELS: Record<IncidentState, string> = {
  reported:      'Reported',
  investigating: 'Investigating',
  managing:      'Managing',
  resolved:      'Resolved',
  closed:        'Closed',
}

interface Props {
  incident: TrafficIncident
  open: boolean
  onClose: () => void
  onTransitioned: (updated: TrafficIncident) => void
}

export function TransitionIncidentModal({ incident, open, onClose, onTransitioned }: Props) {
  const [selected, setSelected] = useState<IncidentState | ''>('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const available = TRANSITIONS[incident.state] ?? []

  async function handleSubmit() {
    if (!selected) return
    setSubmitting(true)
    setError(null)
    try {
      const updated = await incidentService.transition(incident.id, selected)
      onTransitioned(updated)
      onClose()
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { message?: string } } }
      setError(apiErr?.response?.data?.message ?? 'Transition failed.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Update Incident State" maxWidth="sm">
      <div className="space-y-4">
        <div className="flex items-center gap-3 rounded-lg border border-gray-800 bg-gray-800/50 p-3">
          <div className="min-w-0">
            <p className="text-sm font-medium text-white truncate">{incident.title}</p>
            <p className="text-xs text-gray-500 mt-0.5">{incident.incident_type}</p>
          </div>
          <StatusBadge status={incident.state} />
        </div>

        {error && (
          <div className="rounded-lg border border-red-800 bg-red-950 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        {available.length === 0 ? (
          <p className="text-sm text-gray-400">
            This incident is in a terminal state (<strong className="text-white">closed</strong>) and cannot be transitioned further.
          </p>
        ) : (
          <>
            <p className="text-sm text-gray-400">Move to:</p>
            <div className="space-y-2">
              {available.map(state => (
                <label key={state}
                  className={`flex items-center gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                    selected === state
                      ? 'border-cyan-500 bg-cyan-500/10'
                      : 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
                  }`}>
                  <input type="radio" name="state" value={state}
                    checked={selected === state}
                    onChange={() => setSelected(state)}
                    className="text-cyan-500" />
                  <div>
                    <p className="text-sm font-medium text-white">{STATE_LABELS[state]}</p>
                  </div>
                  <StatusBadge status={state} />
                </label>
              ))}
            </div>

            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={onClose}
                className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-400 hover:bg-gray-800">
                Cancel
              </button>
              <button type="button" disabled={!selected || submitting}
                onClick={handleSubmit}
                className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-50">
                {submitting ? 'Updating…' : 'Update State'}
              </button>
            </div>
          </>
        )}
      </div>
    </Modal>
  )
}
