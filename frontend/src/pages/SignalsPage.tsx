import { useEffect, useState } from 'react'
import { signalService } from '@/services/traffic.service'
import type { TrafficSignal, SignalPhase } from '@/types/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { StatusBadge } from '@/components/ui/StatusBadge'

function PhaseTimingRow({ phase }: { phase: SignalPhase }) {
  return (
    <div className="grid grid-cols-4 gap-3 py-2.5 border-t border-slate-100 text-xs">
      <div>
        <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-slate-100 text-slate-600 font-bold text-[10px] mr-1.5">
          {phase.phase_number}
        </span>
        <span className="font-medium text-slate-700">{phase.name}</span>
        {phase.movement && <p className="text-slate-400 mt-0.5 pl-6.5">{phase.movement}</p>}
      </div>
      <div className="text-center">
        <p className="text-[10px] text-slate-400 mb-0.5">Green</p>
        <p className="font-mono font-semibold text-emerald-600">
          {phase.minimum_green_seconds}–{phase.maximum_green_seconds}s
        </p>
      </div>
      <div className="text-center">
        <p className="text-[10px] text-slate-400 mb-0.5">Yellow</p>
        <p className="font-mono font-semibold text-amber-600">{phase.yellow_seconds}s</p>
      </div>
      <div className="text-center">
        <p className="text-[10px] text-slate-400 mb-0.5">All-red</p>
        <p className="font-mono font-semibold text-red-600">{phase.all_red_seconds}s</p>
      </div>
    </div>
  )
}

function SignalCard({ signal }: { signal: TrafficSignal }) {
  const [expanded, setExpanded] = useState(false)
  const [phases, setPhases]     = useState<SignalPhase[]>([])
  const [loading, setLoading]   = useState(false)

  async function toggleExpand() {
    if (!expanded && phases.length === 0) {
      setLoading(true)
      try { const data = await signalService.phases(signal.id); setPhases(data.results) }
      catch { setPhases([]) }
      finally { setLoading(false) }
    }
    setExpanded(v => !v)
  }

  return (
    <div className="card card-hover rounded-xl p-5">
      {/* Card header */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5 mb-0.5">
            <div className={`h-2.5 w-2.5 rounded-full shrink-0 ${signal.is_active ? 'bg-emerald-400' : 'bg-slate-300'}`} />
            <p className="font-semibold text-slate-900 truncate">{signal.name}</p>
          </div>
          <p className="text-xs text-slate-500 pl-5">{signal.intersection_name}</p>
        </div>
        <StatusBadge status={signal.is_active ? 'active' : 'inactive'} />
      </div>

      {signal.controller_type && (
        <p className="mt-2.5 text-xs text-slate-400 pl-5">
          {signal.controller_type}
          {signal.controller_identifier && ` · ${signal.controller_identifier}`}
        </p>
      )}

      {/* Expand phases */}
      <button type="button" onClick={toggleExpand} aria-expanded={expanded}
        className="mt-3.5 flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-800 transition-colors">
        <svg className={`h-3.5 w-3.5 transition-transform ${expanded ? 'rotate-90' : ''}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        {expanded ? 'Hide phases' : 'View phase timing'}
      </button>

      {/* Phase detail */}
      {expanded && (
        <div className="mt-2">
          {loading && <p className="text-xs text-slate-400 py-2">Loading phases…</p>}
          {!loading && phases.length === 0 && (
            <p className="text-xs text-slate-400 py-2">No phases configured.</p>
          )}
          {!loading && phases.length > 0 && (
            <>
              <div className="grid grid-cols-4 gap-3 text-[10px] font-semibold uppercase tracking-wider text-slate-400 pb-1">
                <span>Phase</span>
                <span className="text-center">Green</span>
                <span className="text-center">Yellow</span>
                <span className="text-center">All-red</span>
              </div>
              {phases.map(ph => <PhaseTimingRow key={ph.id} phase={ph} />)}
            </>
          )}
        </div>
      )}
    </div>
  )
}

export function SignalsPage() {
  const [items, setItems]   = useState<TrafficSignal[]>([])
  const [count, setCount]   = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState<string | null>(null)

  async function load() {
    setLoading(true); setError(null)
    try { const data = await signalService.list({ page_size: 50 }); setItems(data.results); setCount(data.count) }
    catch { setError('Could not load signals.') }
    finally { setLoading(false) }
  }

  useEffect(() => { void load() }, [])

  const active   = items.filter(s => s.is_active).length
  const inactive = items.length - active

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Traffic Signals</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {count} signals · {active} active · {inactive} inactive
          {count > 0 && <span className="ml-2 text-slate-400">· click to view phase timing</span>}
        </p>
      </div>

      {loading && <LoadingSpinner />}
      {!loading && error && <ErrorMessage message={error} onRetry={load} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState icon="🚦" title="No signals configured" subtitle="Add traffic signals through the admin panel." />
      )}

      {!loading && !error && items.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map(sig => <SignalCard key={sig.id} signal={sig} />)}
        </div>
      )}
    </div>
  )
}
