import { NavLink } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { ROLES } from '@/types/api'
import type { Role } from '@/types/api'

// SVG icon components — no emoji, clean SaaS look
const Icons = {
  dashboard:  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>,
  incidents:  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>,
  events:     <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
  measure:    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>,
  signals:    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" /></svg>,
  analytics:  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" /></svg>,
  cameras:    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M15 10l4.553-2.069A1 1 0 0121 8.871v6.258a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>,
  roads:      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" /></svg>,
  users:      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>,
  audit:      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>,
}

interface NavItem {
  label: string
  to: string
  icon: React.ReactNode
  roles?: Role[]
  section?: string
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard',       to: '/dashboard',    icon: Icons.dashboard, section: 'Operations' },
  { label: 'Incidents',       to: '/incidents',    icon: Icons.incidents,
    roles: [ROLES.SYSTEM_ADMIN, ROLES.TRAFFIC_CONTROL_OFFICER, ROLES.TRAFFIC_ANALYST, ROLES.LAW_ENFORCEMENT] },
  { label: 'Events',          to: '/events',       icon: Icons.events,
    roles: [ROLES.SYSTEM_ADMIN, ROLES.TRAFFIC_CONTROL_OFFICER, ROLES.TRAFFIC_ANALYST, ROLES.LAW_ENFORCEMENT] },
  { label: 'Measurements',    to: '/measurements', icon: Icons.measure,
    roles: [ROLES.SYSTEM_ADMIN, ROLES.TRAFFIC_CONTROL_OFFICER, ROLES.TRAFFIC_ANALYST, ROLES.CAMERA_TECHNICIAN] },
  { label: 'Traffic Signals', to: '/signals',      icon: Icons.signals,
    roles: [ROLES.SYSTEM_ADMIN, ROLES.TRAFFIC_CONTROL_OFFICER, ROLES.TRAFFIC_ANALYST, ROLES.CAMERA_TECHNICIAN] },
  { label: 'Analytics',       to: '/analytics',    icon: Icons.analytics,
    roles: [ROLES.SYSTEM_ADMIN, ROLES.TRAFFIC_CONTROL_OFFICER, ROLES.TRAFFIC_ANALYST, ROLES.LAW_ENFORCEMENT, ROLES.PAYMENT_FINES_OFFICER] },
  { label: 'Cameras & Sensors', to: '/cameras',   icon: Icons.cameras, section: 'Infrastructure',
    roles: [ROLES.SYSTEM_ADMIN, ROLES.CAMERA_TECHNICIAN, ROLES.TRAFFIC_CONTROL_OFFICER] },
  { label: 'Live Monitoring', to: '/live-monitoring', icon: Icons.cameras, section: 'Operations',
    roles: [ROLES.SYSTEM_ADMIN, ROLES.CAMERA_TECHNICIAN, ROLES.TRAFFIC_CONTROL_OFFICER] },
  { label: 'Video Analysis', to: '/video-analysis', icon: Icons.analytics, section: 'Tools',
    roles: [ROLES.SYSTEM_ADMIN, ROLES.TRAFFIC_ANALYST, ROLES.TRAFFIC_CONTROL_OFFICER, ROLES.CAMERA_TECHNICIAN] },
  { label: 'Road Network',    to: '/roads',        icon: Icons.roads,
    roles: [ROLES.SYSTEM_ADMIN, ROLES.TRAFFIC_CONTROL_OFFICER, ROLES.TRAFFIC_ANALYST] },
  { label: 'Users',           to: '/admin/users',  icon: Icons.users, section: 'Administration',
    roles: [ROLES.SYSTEM_ADMIN] },
  { label: 'Audit Log',       to: '/admin/audit',  icon: Icons.audit,
    roles: [ROLES.SYSTEM_ADMIN] },
]

interface SidebarProps {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const { user, hasAnyRole } = useAuthStore()

  const visibleItems = NAV_ITEMS.filter(item =>
    !item.roles || (user?.roles != null && hasAnyRole(item.roles))
  )

  const sections: { title: string | undefined; items: NavItem[] }[] = []
  for (const item of visibleItems) {
    const last = sections[sections.length - 1]
    if (!last || last.title !== item.section) {
      sections.push({ title: item.section, items: [item] })
    } else {
      last.items.push(item)
    }
  }

  return (
    <>
      {open && (
        <div className="fixed inset-0 z-20 bg-slate-900/40 backdrop-blur-sm lg:hidden"
          onClick={onClose} aria-hidden="true" />
      )}

      <aside className={[
        'fixed top-0 left-0 z-30 flex h-full w-[240px] flex-col',
        'transform transition-transform duration-200 ease-in-out',
        open ? 'translate-x-0' : '-translate-x-full',
        'lg:relative lg:translate-x-0 lg:z-auto',
      ].join(' ')}>

        {/* Brand */}
        <div className="sidebar-brand">
          <div className="sidebar-brand-mark">
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" strokeWidth="0"/>
              <path fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          <div>
            <p className="sidebar-brand-name">TrafficOps</p>
            <p className="sidebar-brand-subtitle">AI Traffic Management</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="sidebar-nav" aria-label="Main navigation">
          {sections.map((section, si) => (
            <div key={si} className={si > 0 ? 'sidebar-section' : ''}>
              {section.title && (
                <p className="sidebar-section-title">
                  {section.title}
                </p>
              )}
              <ul className="sidebar-list" role="list">
                {section.items.map(item => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.to === '/dashboard'}
                      onClick={() => onClose()}
                      className={({ isActive }) => [
                        'sidebar-link',
                        isActive ? 'sidebar-link-active' : '',
                      ].join(' ')}
                    >
                      {({ isActive }) => (
                        <>
                          <span className={isActive ? 'sidebar-link-icon-active' : 'sidebar-link-icon'} aria-hidden="true">
                            {item.icon}
                          </span>
                          {item.label}
                        </>
                      )}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        {/* User info */}
        {user && (
          <div className="sidebar-user-card">
            <div className="flex items-center gap-2.5">
              <div className="sidebar-user-avatar">
                {(user.first_name?.[0] ?? user.username[0]).toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="sidebar-user-name">{user.username}</p>
                <p className="sidebar-user-role">{user.roles[0] ?? 'No role'}</p>
              </div>
            </div>
          </div>
        )}
      </aside>
    </>
  )
}
