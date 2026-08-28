import { useEffect, useState, useCallback } from 'react'
import { userService } from '@/services/admin.service'
import type { AdminUser } from '@/types/api'
import { ROLES } from '@/types/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { Modal } from '@/components/ui/Modal'
import { inputCls } from '@/components/ui/FormField'
import { Pagination, tableCls } from '@/components/ui/DataTable'
import { useAuthStore } from '@/store/authStore'
import { formatDateTime } from '@/utils/time'

const ALL_ROLES = Object.values(ROLES)

function RoleBadge({ role }: { role: string }) {
  return (
    <span className="inline-block rounded-full border border-blue-100 bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
      {role}
    </span>
  )
}

function RoleManageModal({
  user, open, onClose, onSaved,
}: {
  user: AdminUser
  open: boolean
  onClose: () => void
  onSaved: (u: AdminUser) => void
}) {
  const [adding, setAdding] = useState('')
  const [busy,   setBusy]   = useState(false)
  const [err,    setErr]    = useState<string | null>(null)
  const { user: me } = useAuthStore()

  async function assign() {
    if (!adding) return
    setBusy(true); setErr(null)
    try {
      const updated = await userService.assignRole(user.id, adding)
      onSaved(updated)
      setAdding('')
    } catch (e: unknown) {
      const ae = e as { response?: { data?: { message?: string } } }
      setErr(ae?.response?.data?.message ?? 'Failed to assign role.')
    } finally { setBusy(false) }
  }

  async function remove(role: string) {
    if (me?.id === user.id) return
    setBusy(true); setErr(null)
    try {
      await userService.removeRole(user.id, role)
      const list = await userService.list({ page_size: 100 })
      const updated = list.results.find(u => u.id === user.id) ?? user
      onSaved(updated)
    } catch (e: unknown) {
      const ae = e as { response?: { data?: { message?: string } } }
      setErr(ae?.response?.data?.message ?? 'Failed to remove role.')
    } finally { setBusy(false) }
  }

  const available = ALL_ROLES.filter(r => !user.roles.includes(r))

  return (
    <Modal open={open} onClose={onClose} title={`Manage Roles — ${user.username}`} maxWidth="sm">
      <div className="space-y-5">
        {err && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">
            {err}
          </div>
        )}

        {/* Current roles */}
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Current Roles
          </p>
          {user.roles.length === 0 ? (
            <p className="text-sm text-slate-400 italic">No roles assigned.</p>
          ) : (
            <div className="space-y-1.5">
              {user.roles.map(r => (
                <div key={r}
                  className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                  <span className="text-sm font-medium text-slate-700">{r}</span>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => remove(r)}
                    className="text-xs font-medium text-red-600 hover:text-red-800 disabled:opacity-40 transition-colors">
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Add role */}
        {available.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Add Role
            </p>
            <div className="flex gap-2">
              <select
                value={adding}
                onChange={e => setAdding(e.target.value)}
                className={inputCls}
              >
                <option value="">— Select role —</option>
                {available.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
              <button
                type="button"
                disabled={!adding || busy}
                onClick={assign}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 whitespace-nowrap transition-colors shadow-sm">
                {busy ? '…' : 'Add'}
              </button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}

export function UserManagementPage() {
  const [users,      setUsers]      = useState<AdminUser[]>([])
  const [count,      setCount]      = useState(0)
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState<string | null>(null)
  const [page,       setPage]       = useState(1)
  const [roleTarget, setRoleTarget] = useState<AdminUser | null>(null)
  const [toggling,   setToggling]   = useState<number | null>(null)
  const { user: me } = useAuthStore()

  const load = useCallback(async (p = 1) => {
    setLoading(true); setError(null)
    try {
      const data = await userService.list({ page: p, page_size: 20 })
      setUsers(data.results)
      setCount(data.count)
    } catch {
      setError('Could not load users. Only System Administrators can access this page.')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { void load(1) }, [load])

  async function toggleStatus(user: AdminUser) {
    if (me?.id === user.id) return
    setToggling(user.id)
    try {
      const updated = await userService.setStatus(user.id, !user.is_active)
      setUsers(prev => prev.map(u => u.id === updated.id ? updated : u))
    } catch { /* silently ignore */ }
    finally { setToggling(null) }
  }

  const totalPages = Math.ceil(count / 20)

  return (
    <div className="space-y-5">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-semibold text-slate-900">User Management</h1>
        <p className="text-sm text-slate-500 mt-0.5">{count} users · manage roles and account status</p>
      </div>

      {loading && <LoadingSpinner />}
      {!loading && error && <ErrorMessage message={error} onRetry={() => load(page)} />}
      {!loading && !error && users.length === 0 && (
        <EmptyState icon="👥" title="No users found" subtitle="No users are registered in the system." />
      )}

      {!loading && !error && users.length > 0 && (
        <div className={tableCls.wrapper}>
          <table className={tableCls.table}>
            <thead className={tableCls.thead}>
              <tr>
                <th className={tableCls.th}>Username</th>
                <th className={tableCls.th}>Email</th>
                <th className={tableCls.th}>Roles</th>
                <th className={tableCls.th}>Status</th>
                <th className={tableCls.th}>Joined</th>
                <th className={tableCls.th}>Last Login</th>
                <th className={tableCls.th}>Actions</th>
              </tr>
            </thead>
            <tbody className={tableCls.tbody}>
              {users.map(u => (
                <tr key={u.id} className={tableCls.tr}>
                  <td className="px-4 py-3">
                    <span className="font-semibold text-slate-900">{u.username}</span>
                    {u.id === me?.id && (
                      <span className="ml-1.5 rounded-full bg-blue-50 px-1.5 py-0.5 text-[10px] font-semibold text-blue-600 border border-blue-100">
                        you
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs">{u.email || '—'}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {u.roles.length === 0
                        ? <span className="text-xs italic text-slate-400">None</span>
                        : u.roles.map(r => <RoleBadge key={r} role={r} />)}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={u.is_active ? 'active' : 'inactive'} dot />
                  </td>
                  <td className="px-4 py-3 text-slate-400 text-xs whitespace-nowrap">
                    {formatDateTime(u.date_joined)}
                  </td>
                  <td className="px-4 py-3 text-slate-400 text-xs whitespace-nowrap">
                    {u.last_login ? formatDateTime(u.last_login) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1.5">
                      <button
                        type="button"
                        onClick={() => setRoleTarget(u)}
                        className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors shadow-sm">
                        Roles
                      </button>
                      {u.id !== me?.id && (
                        <button
                          type="button"
                          disabled={toggling === u.id}
                          onClick={() => toggleStatus(u)}
                          className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-50 whitespace-nowrap ${
                            u.is_active
                              ? 'border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
                              : 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                          }`}>
                          {toggling === u.id ? '…' : u.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      )}
                    </div>
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

      {roleTarget && (
        <RoleManageModal
          user={roleTarget}
          open={!!roleTarget}
          onClose={() => setRoleTarget(null)}
          onSaved={updated => {
            setUsers(prev => prev.map(u => u.id === updated.id ? updated : u))
            setRoleTarget(updated)
          }}
        />
      )}
    </div>
  )
}
