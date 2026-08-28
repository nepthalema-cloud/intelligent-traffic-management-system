// React import not required with the new JSX runtime

interface DataTableProps<T> {
  columns: { key: string; title: string }[]
  data: T[]
}

export function DataTable<T>({ columns, data }: DataTableProps<T>) {
  return (
    <div className="overflow-auto">
      <table className="w-full table-auto border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-slate-500">
            {columns.map(c => <th key={c.key} className="px-3 py-2">{c.title}</th>)}
          </tr>
        </thead>
        <tbody>
          {data.map((row, ri) => (
            <tr key={ri} className={ri % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
              {columns.map(col => <td key={col.key} className="px-3 py-2 align-top">{(row as any)[col.key]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default DataTable
/**
 * DataTable — consistent light-theme table for all data pages.
 * Replaces bg-gray-900 / border-gray-800 pattern used in legacy pages.
 */
export const tableCls = {
  wrapper:  'overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm',
  table:    'w-full text-sm',
  thead:    'border-b border-slate-100 bg-slate-50',
  th:       'px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500',
  thRight:  'px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500',
  tbody:    'divide-y divide-slate-100',
  tr:       'hover:bg-slate-50/70 transition-colors',
  td:       'px-4 py-3 text-slate-700',
  tdRight:  'px-4 py-3 text-right text-slate-700',
  tdMuted:  'px-4 py-3 text-slate-400',
  tdMono:   'px-4 py-3 font-mono text-xs text-slate-600',
}

/** Shared select / input classes for page-level filters */
export const filterInputCls =
  'rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 ' +
  'shadow-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20'

/** Shared pagination row */
interface PaginationProps {
  page: number
  totalPages: number
  total: number
  onPrev: () => void
  onNext: () => void
}

export function Pagination({ page, totalPages, total, onPrev, onNext }: PaginationProps) {
  if (totalPages <= 1) return null
  return (
    <div className="flex items-center justify-between text-sm text-slate-500">
      <span>
        Page <span className="font-medium text-slate-700">{page}</span> of {totalPages}
        <span className="ml-2 text-slate-400">({total} total)</span>
      </span>
      <div className="flex gap-2">
        <button
          disabled={page <= 1}
          onClick={onPrev}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-slate-600 hover:bg-slate-50 disabled:opacity-40 transition-colors shadow-sm"
        >
          Previous
        </button>
        <button
          disabled={page >= totalPages}
          onClick={onNext}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-slate-600 hover:bg-slate-50 disabled:opacity-40 transition-colors shadow-sm"
        >
          Next
        </button>
      </div>
    </div>
  )
}
