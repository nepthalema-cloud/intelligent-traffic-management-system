import type { CameraState, CameraConnectionStatus } from '@/types/api'

const STATE_CONFIG: Record<CameraState, { icon: string; bg: string; text: string; ring: string }> = {
  saved:            { icon: '○', bg: 'bg-slate-100',  text: 'text-slate-600',  ring: 'ring-slate-300' },
  rtsp_unreachable: { icon: '✕', bg: 'bg-red-50',     text: 'text-red-700',    ring: 'ring-red-200'   },
  auth_failed:      { icon: '⚠', bg: 'bg-red-50',     text: 'text-red-700',    ring: 'ring-red-200'   },
  stream_connected: { icon: '↗', bg: 'bg-amber-50',   text: 'text-amber-700',  ring: 'ring-amber-200' },
  hls_available:    { icon: '▶', bg: 'bg-blue-50',    text: 'text-blue-700',   ring: 'ring-blue-200'  },
  ai_processing:    { icon: '⚡', bg: 'bg-cyan-50',    text: 'text-cyan-700',   ring: 'ring-cyan-200'  },
  live:             { icon: '●', bg: 'bg-emerald-50',  text: 'text-emerald-700',ring: 'ring-emerald-200'},
}

interface Props {
  status: CameraConnectionStatus
  showDetail?: boolean
}

export function CameraConnectionBadge({ status, showDetail = false }: Props) {
  const cfg = STATE_CONFIG[status.state] ?? STATE_CONFIG.saved

  return (
    <div>
      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${cfg.bg} ${cfg.text} ${cfg.ring}`}>
        <span className={status.state === 'live' ? 'animate-pulse' : ''}>{cfg.icon}</span>
        {status.state_label}
      </span>
      {showDetail && status.detail && (
        <p className="mt-1 text-xs text-slate-500">{status.detail}</p>
      )}
    </div>
  )
}
