import { useEffect, useRef, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useTheme } from '@/components/ui/ThemeProvider'
import { useAuthStore } from '@/store/authStore'
import { SystemStatusBadge } from '@/components/ui/SystemStatusBadge'

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/incidents': 'Traffic Incidents',
  '/events': 'Traffic Events',
  '/measurements': 'Traffic Measurements',
  '/signals': 'Traffic Signals',
  '/cameras': 'Cameras & Sensors',
  '/live-monitoring': 'Live Monitoring',
  '/roads': 'Road Network',
  '/analytics': 'Analytics',
  '/video-analysis': 'Video Analysis',
  '/profile': 'Profile',
  '/settings': 'Settings',
  '/admin/users': 'User Management',
  '/admin/audit': 'Audit Log',
}

interface TopBarProps {
  onMenuClick: () => void
}

export function TopBar({ onMenuClick }: TopBarProps) {
  const { user, logout } = useAuthStore()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!menuOpen) return

    function handlePointerDown(event: MouseEvent) {
      const target = event.target as Node
      if (menuRef.current && !menuRef.current.contains(target)) {
        setMenuOpen(false)
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setMenuOpen(false)
      }
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [menuOpen])

  const pageTitle = PAGE_TITLES[location.pathname] ?? 'TrafficOps'

  async function handleLogout() {
    setMenuOpen(false)
    await logout()
    navigate('/login', { replace: true })
  }

  const initials = user
    ? (user.first_name?.[0] ?? user.username[0]).toUpperCase()
    : '?'

  const themeLabel = theme === 'dark' ? 'Light' : 'Dark'

  return (
    <header className="topbar-shell">
      <div className="topbar-left">
        <button type="button"
          className="topbar-menu-button lg:hidden"
          onClick={onMenuClick} aria-label="Open navigation">
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <div>
          <h1 className="topbar-title">{pageTitle}</h1>
        </div>
      </div>

      <div className="topbar-right">
        <SystemStatusBadge />

        <div className="topbar-actions">
          <button
            type="button"
            onClick={(event) => {
              event.preventDefault()
              event.stopPropagation()
              toggleTheme()
            }}
            className="topbar-theme-button"
            aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            <span aria-hidden="true">{theme === 'dark' ? '☀' : '☾'}</span>
            <span className="hidden sm:inline">{themeLabel}</span>
          </button>

          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={(event) => {
                event.preventDefault()
                event.stopPropagation()
                setMenuOpen(v => !v)
              }}
              className="topbar-user-button"
              aria-haspopup="true"
              aria-expanded={menuOpen}
            >
              <span className="topbar-user-avatar">{initials}</span>
              <span className="hidden sm:block topbar-user-name">{user?.username ?? '—'}</span>
              <svg className="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {menuOpen && (
              <div className="topbar-menu-panel">
                {user && (
                  <div className="topbar-menu-user">
                    <p className="topbar-menu-user-name">{user.username}</p>
                    <p className="topbar-menu-user-role">{user.roles[0] ?? 'No role'}</p>
                  </div>
                )}

                <button type="button" onClick={() => { setMenuOpen(false); navigate('/profile') }} className="topbar-menu-action">
                  Profile
                </button>

                <button type="button" onClick={() => { setMenuOpen(false); navigate('/settings') }} className="topbar-menu-action">
                  Settings
                </button>

                <button type="button" onClick={handleLogout} className="topbar-menu-signout">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h6a2 2 0 012 2v1" />
                  </svg>
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
