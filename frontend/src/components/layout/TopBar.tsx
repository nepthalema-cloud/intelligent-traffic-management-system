import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { SystemStatusBadge } from '@/components/ui/SystemStatusBadge'

const PAGE_TITLES: Record<string, string> = {
  '/dashboard':    'Dashboard',
  '/incidents':    'Traffic Incidents',
  '/events':       'Traffic Events',
  '/measurements': 'Traffic Measurements',
  '/signals':      'Traffic Signals',
  '/cameras':      'Cameras & Sensors',
  '/roads':        'Road Network',
  '/analytics':    'Analytics',
  '/admin/users':  'User Management',
  '/admin/audit':  'Audit Log',
}

interface TopBarProps {
  onMenuClick: () => void
}

export function TopBar({ onMenuClick }: TopBarProps) {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  const pageTitle = PAGE_TITLES[location.pathname] ?? 'TrafficOps'

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  const initials = user
    ? (user.first_name?.[0] ?? user.username[0]).toUpperCase()
    : '?'

  return (
    <header className="flex h-[60px] shrink-0 items-center justify-between bg-white px-4 lg:px-6">
      {/* Left */}
      <div className="flex items-center gap-3">
        {/* Mobile hamburger */}
        <button type="button"
          className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 lg:hidden"
          onClick={onMenuClick} aria-label="Open navigation">
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <div>
          <h1 className="text-base font-semibold text-slate-900">{pageTitle}</h1>
        </div>
      </div>

      {/* Right */}
      <div className="flex items-center gap-3">
        {/* System status badge — honest, from backend */}
        <SystemStatusBadge />

        {/* User menu */}
        <div className="relative">
          <button type="button"
            onClick={() => setMenuOpen(v => !v)}
            className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-slate-50 transition-colors"
            aria-haspopup="true" aria-expanded={menuOpen}>
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white shadow-sm">
              {initials}
            </span>
            <span className="hidden sm:block text-sm font-medium text-slate-700">
              {user?.username ?? '—'}
            </span>
            <svg className="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {menuOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} aria-hidden="true" />
              <div className="absolute right-0 z-20 mt-1.5 w-52 rounded-xl border border-slate-200 bg-white shadow-lg py-1">
                {user && (
                  <div className="border-b border-slate-100 px-4 py-3">
                    <p className="text-sm font-semibold text-slate-900">{user.username}</p>
                    <p className="text-xs text-slate-500 mt-0.5 truncate">{user.roles[0] ?? 'No role'}</p>
                  </div>
                )}
                <button type="button" onClick={handleLogout}
                  className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h6a2 2 0 012 2v1" />
                  </svg>
                  Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
