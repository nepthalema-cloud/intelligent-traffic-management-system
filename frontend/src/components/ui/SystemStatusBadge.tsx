/**
 * SystemStatusBadge — honest system mode indicator.
 *
 * Derives state from GET /api/v1/system/status/ — never hardcoded.
 * Shows aggregate mode + per-camera count.
 *
 * live      → green  ● Live (all cameras: connected + HLS + AI active)
 * degraded  → amber  ◐ Degraded (some cameras live, some not)
 * demo      → blue   ○ Demo Mode (no live cameras)
 * offline   → slate  ○ No Camera Feed
 * loading   → gray   Checking…
 */

import { useCallback, useState } from 'react'
import type { SystemMode } from '@/types/api'
import { systemService } from '@/services/system.service'
import { usePolling } from '@/hooks/usePolling'

interface SystemStatusData {
  mode: SystemMode
  cameras_total: number
  cameras_connected: number
  cameras_live: number
  ai_processing_active: boolean
  cameras_with_ai: number
}

const CONFIG: Record<SystemMode | 'loading', { dot: string; text: string; label: (d?: SystemStatusData) => string }> = {
  live:     {
    dot:  'bg-emerald-500 animate-pulse',
    text: 'text-emerald-700',
    label: (d) => d && d.cameras_live < d.cameras_total
      ? `Live (${d.cameras_live}/${d.cameras_total})`
      : 'Live',
  },
  degraded: {
    dot:  'bg-amber-400',
    text: 'text-amber-700',
    label: (d) => d
      ? `Degraded — ${d.cameras_live} live, ${d.cameras_total - d.cameras_live} offline`
      : 'Degraded',
  },
  demo:     { dot: 'bg-blue-400',   text: 'text-blue-700',   label: () => 'Demo Mode' },
  offline:  { dot: 'bg-slate-400',  text: 'text-slate-600',  label: () => 'No Camera Feed' },
  loading:  { dot: 'bg-slate-300',  text: 'text-slate-400',  label: () => 'Checking…' },
}

export function SystemStatusBadge() {
  const [data, setData] = useState<SystemStatusData | null>(null)
  const [mode, setMode] = useState<SystemMode | 'loading'>('loading')

  const load = useCallback(() => {
    systemService.status()
      .then(s => {
        setData(s as unknown as SystemStatusData)
        setMode(s.mode)
      })
      .catch(() => setMode('offline'))
  }, [])

  // Poll every 30s — matches AI measurement interval
  usePolling(load, 30_000)

  const cfg = CONFIG[mode]
  const label = cfg.label(data ?? undefined)

  const tooltip = data
    ? `${data.cameras_connected}/${data.cameras_total} cameras connected · ${data.cameras_with_ai} with AI active · ${data.ai_processing_active ? 'AI processing' : 'AI offline'}`
    : undefined

  return (
    <span
      className={`hidden items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium sm:flex ${cfg.text}`}
      title={tooltip}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
      {label}
    </span>
  )
}
