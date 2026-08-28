/**
 * Lightweight relative time formatter.
 * Does not depend on any external library.
 */
export function formatRelative(isoString: string): string {
  const now = Date.now()
  const then = new Date(isoString).getTime()
  const diffMs = now - then
  const diffSec = Math.floor(diffMs / 1000)

  if (diffSec < 60)  return 'just now'
  if (diffSec < 3600) {
    const m = Math.floor(diffSec / 60)
    return `${m}m ago`
  }
  if (diffSec < 86400) {
    const h = Math.floor(diffSec / 3600)
    return `${h}h ago`
  }
  const d = Math.floor(diffSec / 86400)
  if (d === 1) return 'yesterday'
  if (d < 30) return `${d}d ago`
  return new Date(isoString).toLocaleDateString()
}

export function formatDateTime(isoString: string): string {
  return new Date(isoString).toLocaleString()
}
