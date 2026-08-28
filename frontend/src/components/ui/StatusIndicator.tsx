// React import not required with the new JSX runtime

export function StatusIndicator({ status = 'unknown', size = 2 }: { status?: 'online'|'offline'|'degraded'|'unknown'; size?: number }) {
  const map: Record<string,string> = {
    online: 'bg-emerald-400',
    offline: 'bg-red-500',
    degraded: 'bg-amber-500',
    unknown: 'bg-slate-300',
  }
  return <span className={[`inline-block h-${size} w-${size} rounded-full`, map[status]].join(' ')} />
}

export default StatusIndicator
