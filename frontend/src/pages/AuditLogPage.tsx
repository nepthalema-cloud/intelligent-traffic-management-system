import { useEffect, useState } from 'react'
import { auditService } from '@/services/admin.service'
import type { AuditEvent } from '@/types/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { Pagination, tableCls, filterInputCls } from '@/components/ui/DataTable'
import { formatDateTime } from '@/utils/time'

const OUTCOME_CFG: Record<string, { cls: string; dot: string }> = {
  success: { cls: 'text-emerald-700 bg-emerald-50 border-emerald-100', dot: 'bg-emerald-400' },
  failure: { cls: 'text-red-700 bg-red-50 border-red-100',             dot: 'bg-red-400'     },
  denied:  { cls: 'text-amber-700 bg-amber-50 border-amber-100',       dot: 'bg-amber-400'   },
}

function OutcomeBadge({ outcome }: { outcome: string }) {
  const cfg = OUTCOME_CFG[outcome]
  if (!cfg) return <span className="text-slate-400 text-xs">{outcome}</span>
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${cfg.cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
      {outcome}
    </span>
  )
}

export function AuditLogPage() {
  const [items,   setItems]   = useState<AuditEvent[]>([])
  const [count,   setCount]   = useState(0)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)
  const [page,    setPage]    = useState(1)
  const [filter,  setFilter]  = useState({ action: '', outcome: '' })

  async function load(p = 1) {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string | number> = { page: p, page_size: 20 }
      if (filter.action)  params['action']  = filter.action
      if (filter.outcome) params['outcome'] = filter.outcome
      const data = await auditService.list(params)
      setItems(data.results)
      setCount(data.count)
    } catch {
      setError('Could not load audit events. Only System Administrators can access this page.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { setPage(1); void load(1) }, [filter.action, filter.outcome])

  const totalPages = Math.ceil(count / 20)

  return (
    <div className="space-y-5">
      {/* Page header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Audit Log</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {count} events · read-only · newest first
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-2">
          <input
            type="text"
            placeholder="Filter by action…"
            value={filter.action}
            onChange={e => setFilter(f => ({ ...f, action: e.target.value }))}
            className={`${filterInputCls} w-44`}
            aria-label="Filter by action"
          />
          <select
            value={filter.outcome}
            onChange={e => setFilter(f => ({ ...f, outcome: e.target.value }))}
            className={filterInputCls}
            aria-label="Filter by outcome"
          >
            <option value="">All outcomes</option>
            <option value="success">Success</option>
            <option value="failure">Failure</option>
            <option value="denied">Denied</option>
          </select>
        </div>
      </div>

      {loading && <LoadingSpinner />}
      {!loading && error && <ErrorMessage message={error} onRetry={() => load(page)} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState icon="📋" title="No audit events found"
          subtitle="No events match the current filters." />
      )}

      {!loading && !error && items.length > 0 && (
        <div className={tableCls.wrapper}>
          <table className={tableCls.table}>
            <thead className={tableCls.thead}>
              <tr>
                <th className={tableCls.th}>Timestamp</th>
                <th className={tableCls.th}>Actor</th>
                <th className={tableCls.th}>Action</th>
                <th className={tableCls.th}>Target</th>
                <th className={tableCls.th}>Outcome</th>
                <th className={tableCls.th}>IP Address</th>
              </tr>
            </thead>
            <tbody className={tableCls.tbody}>
              {items.map(ev => (
                <tr key={ev.id} className={tableCls.tr}>
                  <td className="px-4 py-3 text-slate-400 whitespace-nowrap text-xs">
                    {formatDateTime(ev.timestamp)}
                  </td>
                  <td className="px-4 py-3 text-sm font-medium text-slate-700">
                    {ev.actor_username ?? (
                      <span className="italic text-slate-400">system</span>
                    )}
                  </td>
                  <td className="px-4 py-3 max-w-[200px] truncate">
                    <span className="font-mono text-xs text-blue-600 bg-blue-50 rounded px-1.5 py-0.5">
                      {ev.action}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {ev.target_type ? (
                      <span>
                        {ev.target_type}
                        {ev.target_id && (
                          <span className="ml-1 text-slate-400 font-mono">#{ev.target_id}</span>
                        )}
                      </span>
                    ) : (
                      <span className="text-slate-300">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <OutcomeBadge outcome={ev.outcome} />
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-400">
                    {ev.ip_address ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Pagination
        page={page}
        totalPages={totalPages}
        total={count}
        onPrev={() => { const p = page - 1; setPage(p); void load(p) }}
        onNext={() => { const p = page + 1; setPage(p); void load(p) }}
      />
    </div>
  )
}
